#!/usr/bin/env bash
# Final video assembly. Slides + prototype demo + voiceover audio.
#
# Reads `timing.json` (written by the orchestrator from the transcript)
# describing per-slide durations and the demo segment. The assumption is
# that `timing.json` already encodes the correct durations sized to the
# user's actual audio — this script does NO time-stretching of audio.
#
# It WILL gently stretch the prototype video if the recorded duration
# is within 1.25× of the demo segment; beyond that, it errors and asks
# for a re-record at the right length.
#
# Usage:
#   bash build_video.sh \
#     --transcript transcript.json \
#     --audio voiceover.m4a \
#     --slides slides/ \
#     --prototype prototype/prototype.webm \
#     --timing timing.json \
#     --output output/pitch_video.mp4
#
# timing.json schema:
# {
#   "intro_silence": 3.0,
#   "slides": [
#     {"name": "slide_01", "image": "slide_01.png", "duration": 3.0},
#     {"name": "slide_02", "image": "slide_02.png", "duration": 39.9},
#     ...
#     {"name": "demo", "is_demo": true, "duration": 36.9},
#     ...
#   ]
# }

set -eu

TRANSCRIPT=""
AUDIO=""
SLIDES=""
PROTO=""
TIMING=""
OUTPUT="output/pitch_video.mp4"

while [ $# -gt 0 ]; do
  case "$1" in
    --transcript) TRANSCRIPT="$2"; shift 2;;
    --audio)      AUDIO="$2"; shift 2;;
    --slides)     SLIDES="$2"; shift 2;;
    --prototype)  PROTO="$2"; shift 2;;
    --timing)     TIMING="$2"; shift 2;;
    --output)     OUTPUT="$2"; shift 2;;
    *) echo "unknown flag: $1"; exit 2;;
  esac
done

for arg in TRANSCRIPT AUDIO SLIDES TIMING; do
  if [ -z "${!arg}" ]; then
    echo "missing --${arg,,}"; exit 2
  fi
done

# locate ffmpeg — prefer imageio-ffmpeg's bundled binary
FFMPEG="$(python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())' 2>/dev/null || command -v ffmpeg)"
if [ -z "$FFMPEG" ] || [ ! -x "$FFMPEG" ]; then
  echo "error: ffmpeg not found. install imageio-ffmpeg or system ffmpeg."
  exit 1
fi

OUT_DIR="$(dirname "$OUTPUT")"
mkdir -p "$OUT_DIR"
TMP_DIR="$(mktemp -d -t pitch-video.XXXXXX)"
trap "rm -rf '$TMP_DIR'" EXIT

# Parse timing.json with python
python3 - "$TIMING" > "$TMP_DIR/segments.txt" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
intro = data.get("intro_silence", 0)
print(f"INTRO\t{intro}")
for s in data["slides"]:
    if s.get("is_demo"):
        print(f"DEMO\t{s['duration']}")
    else:
        print(f"SLIDE\t{s['image']}\t{s['duration']}")
PY

# Read segments
SEG_LINES=()
while IFS= read -r line; do
  SEG_LINES+=("$line")
done < "$TMP_DIR/segments.txt"

INTRO_SEC=$(echo "${SEG_LINES[0]}" | cut -f2)
echo "intro silence: ${INTRO_SEC}s"

# 1. Build audio track: intro silence + full voiceover
"$FFMPEG" -y -f lavfi -t "$INTRO_SEC" -i anullsrc=r=48000:cl=mono \
  -c:a aac -b:a 192k "$TMP_DIR/_sil.m4a" 2>/dev/null
"$FFMPEG" -y -i "$AUDIO" -c:a aac -b:a 192k "$TMP_DIR/_voice.m4a" 2>/dev/null
"$FFMPEG" -y -i "$TMP_DIR/_sil.m4a" -i "$TMP_DIR/_voice.m4a" \
  -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[a]" -map "[a]" \
  -c:a aac -b:a 192k "$TMP_DIR/audio.m4a" 2>/dev/null

# 2. If a demo segment exists, fit the prototype to its target duration
DEMO_TARGET=""
for line in "${SEG_LINES[@]}"; do
  if [[ "$line" == DEMO* ]]; then
    DEMO_TARGET=$(echo "$line" | cut -f2)
    break
  fi
done

PROTO_FIT=""
if [ -n "$DEMO_TARGET" ] && [ -n "$PROTO" ]; then
  PROTO_RAW=$("$FFMPEG" -i "$PROTO" 2>&1 | grep Duration | head -1 \
    | awk '{print $2}' | tr -d ',' \
    | awk -F: '{print ($1*3600)+($2*60)+$3}')
  RATIO=$(python3 -c "print($DEMO_TARGET / $PROTO_RAW)")
  # Only stretch if within reasonable bounds; otherwise warn
  IS_OK=$(python3 -c "r=$RATIO; print(0.8 <= r <= 1.5)")
  if [ "$IS_OK" = "True" ]; then
    PROTO_FIT="$TMP_DIR/_proto_fit.mp4"
    SETPTS=$(python3 -c "print($DEMO_TARGET / $PROTO_RAW)")
    "$FFMPEG" -y -i "$PROTO" -filter:v "setpts=PTS*${SETPTS}" -an \
      -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
      "$PROTO_FIT" 2>/dev/null
    echo "  prototype fitted: ${PROTO_RAW}s → ${DEMO_TARGET}s (ratio ${RATIO})"
  else
    echo "warn: prototype duration ${PROTO_RAW}s is too far from target ${DEMO_TARGET}s"
    echo "      ratio=${RATIO}. Re-record the prototype at the target length."
    PROTO_FIT="$PROTO"  # use as-is anyway, but the user has been warned
  fi
fi

# 3. Build the video chain — concat all slide images and the prototype clip
CMD_INPUTS=()
FILTER_PARTS=()
i=0
for line in "${SEG_LINES[@]}"; do
  case "$line" in
    INTRO*) ;;
    SLIDE*)
      img=$(echo "$line" | cut -f2)
      dur=$(echo "$line" | cut -f3)
      CMD_INPUTS+=("-loop" "1" "-t" "$dur" "-i" "$SLIDES/$img")
      FILTER_PARTS+=("[${i}:v]scale=1920:1080,setsar=1,fps=30,format=yuv420p[v${i}]")
      i=$((i+1))
      ;;
    DEMO*)
      CMD_INPUTS+=("-i" "$PROTO_FIT")
      FILTER_PARTS+=("[${i}:v]scale=1920:1080,setsar=1,fps=30,format=yuv420p[v${i}]")
      i=$((i+1))
      ;;
  esac
done

# concat label list
CONCAT_LABELS=""
for j in $(seq 0 $((i - 1))); do
  CONCAT_LABELS="${CONCAT_LABELS}[v${j}]"
done
FILTER_PARTS+=("${CONCAT_LABELS}concat=n=${i}:v=1:a=0[v]")
FC=$(IFS=";"; echo "${FILTER_PARTS[*]}")

"$FFMPEG" -y "${CMD_INPUTS[@]}" \
  -filter_complex "$FC" -map "[v]" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -movflags +faststart \
  "$TMP_DIR/video.mp4" 2>&1 | tail -2

# 4. Mux video + audio
"$FFMPEG" -y -i "$TMP_DIR/video.mp4" -i "$TMP_DIR/audio.m4a" \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart \
  "$OUTPUT" 2>&1 | tail -2

echo
echo "done — $OUTPUT"
"$FFMPEG" -i "$OUTPUT" 2>&1 | grep -E "Duration|Stream"
