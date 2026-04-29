#!/usr/bin/env python3
"""Audio editing helpers for the alignment-fix loop.

Operations (subcommands):

  atempo         apply a tempo change (speed up / slow down) to a region
  splice         replace a region with a new recording
  trim_silence   collapse pauses longer than --max-pause to --target-pause
  hold           extend the LAST frame of a video clip by N seconds (no audio change)

Safety bounds (rejected with an error if exceeded — re-record instead):

  atempo:    0.92 ≤ rate ≤ 1.25  (1.18+ flagged as "noticeable")
  hold:      max +3 seconds
  trim:      collapses pauses >2.0s to 0.6s; never strips all silence

Examples:
  python audio_edit.py atempo --input voice.m4a --output fast.m4a --rate 1.10 --start 60 --end 95
  python audio_edit.py splice --input voice.m4a --patch newchunk.m4a --start 60 --end 90 --output spliced.m4a
  python audio_edit.py trim_silence --input voice.m4a --output trimmed.m4a
  python audio_edit.py hold --input prototype.webm --output held.mp4 --extra 2.5
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def ffmpeg_path():
    """Return path to ffmpeg, preferring imageio-ffmpeg's bundled binary."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return shutil.which("ffmpeg") or "ffmpeg"


FF = ffmpeg_path()


def _run(cmd):
    """Run a subprocess and surface errors."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("ffmpeg stderr:", r.stderr[-2000:], file=sys.stderr)
        raise RuntimeError(f"command failed: {' '.join(cmd[:4])}...")


# ── atempo ──────────────────────────────────────────────────────────────────

ATEMPO_SAFE = (0.92, 1.18)
ATEMPO_HARD = (0.85, 1.25)


def atempo(input_path, output_path, rate, start=None, end=None):
    if not (ATEMPO_HARD[0] <= rate <= ATEMPO_HARD[1]):
        raise SystemExit(
            f"atempo rate {rate} outside hard bounds {ATEMPO_HARD}. "
            f"Re-record this section instead."
        )
    if not (ATEMPO_SAFE[0] <= rate <= ATEMPO_SAFE[1]):
        print(f"  warn: atempo {rate} is noticeable. "
              f"Safe range is {ATEMPO_SAFE}.", file=sys.stderr)

    if start is None and end is None:
        # whole-file atempo
        cmd = [FF, "-y", "-i", str(input_path),
               "-filter:a", f"atempo={rate}",
               "-c:a", "aac", "-b:a", "192k",
               str(output_path)]
        _run(cmd)
        return

    # region-only atempo: split → atempo middle → concat
    if start is None: start = 0
    if end is None:
        # query duration via ffprobe-like ffmpeg call
        r = subprocess.run([FF, "-i", str(input_path)],
                           capture_output=True, text=True)
        for line in r.stderr.splitlines():
            if "Duration:" in line:
                t = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = t.split(":")
                end = int(h) * 3600 + int(m) * 60 + float(s)
                break

    # build via filter_complex: [0]atrim=0:start[a]; [0]atrim=start:end,atempo=R[b]; [0]atrim=end[c]; concat
    fc = (
        f"[0:a]atrim=0:{start}[a];"
        f"[0:a]atrim={start}:{end},asetpts=PTS-STARTPTS,atempo={rate}[b];"
        f"[0:a]atrim={end},asetpts=PTS-STARTPTS[c];"
        f"[a][b][c]concat=n=3:v=0:a=1[out]"
    )
    cmd = [FF, "-y", "-i", str(input_path),
           "-filter_complex", fc, "-map", "[out]",
           "-c:a", "aac", "-b:a", "192k",
           str(output_path)]
    _run(cmd)


# ── splice ──────────────────────────────────────────────────────────────────

def splice(input_path, patch_path, output_path, start, end):
    """Replace audio[start:end] with the contents of patch_path."""
    fc = (
        f"[0:a]atrim=0:{start},asetpts=PTS-STARTPTS[a];"
        f"[1:a]asetpts=PTS-STARTPTS[b];"
        f"[0:a]atrim={end},asetpts=PTS-STARTPTS[c];"
        f"[a][b][c]concat=n=3:v=0:a=1[out]"
    )
    cmd = [FF, "-y", "-i", str(input_path), "-i", str(patch_path),
           "-filter_complex", fc, "-map", "[out]",
           "-c:a", "aac", "-b:a", "192k",
           str(output_path)]
    _run(cmd)


# ── trim silence ────────────────────────────────────────────────────────────

def trim_silence(input_path, output_path, max_pause=2.0, target_pause=0.6,
                 noise_db=-30):
    """Detect silences > max_pause and collapse each to target_pause."""
    # Use ffmpeg silencedetect to find silence ranges
    r = subprocess.run(
        [FF, "-i", str(input_path),
         "-af", f"silencedetect=n={noise_db}dB:d={max_pause}",
         "-f", "null", "-"],
        capture_output=True, text=True
    )
    silences = []
    cur_start = None
    for line in r.stderr.splitlines():
        if "silence_start:" in line:
            cur_start = float(line.split("silence_start:")[1].strip())
        elif "silence_end:" in line and cur_start is not None:
            end = float(line.split("silence_end:")[1].split("|")[0].strip())
            silences.append((cur_start, end))
            cur_start = None

    if not silences:
        # no over-long silences; just copy
        _run([FF, "-y", "-i", str(input_path), "-c", "copy", str(output_path)])
        return

    # Build piecewise concat: keep audio outside silences, insert target_pause silence in their place
    # Simplest approach: split input into chunks bounded by silence, concat with explicit silence between
    parts = []
    cursor = 0.0
    for sil_start, sil_end in silences:
        if sil_start > cursor:
            parts.append(("keep", cursor, sil_start))
        parts.append(("pause",))
        cursor = sil_end
    parts.append(("keep", cursor, None))  # final chunk

    inputs = ["-i", str(input_path), "-f", "lavfi", "-t", str(target_pause),
              "-i", "anullsrc=r=48000:cl=mono"]
    fc_parts = []
    concat_inputs = []
    for i, p in enumerate(parts):
        if p[0] == "keep":
            s, e = p[1], p[2]
            atrim = f"atrim={s}" + (f":{e}" if e is not None else "")
            fc_parts.append(f"[0:a]{atrim},asetpts=PTS-STARTPTS[k{i}]")
            concat_inputs.append(f"[k{i}]")
        else:
            fc_parts.append(f"[1:a]asetpts=PTS-STARTPTS[p{i}]")
            concat_inputs.append(f"[p{i}]")
    fc_parts.append(f"{''.join(concat_inputs)}concat=n={len(concat_inputs)}:v=0:a=1[out]")
    fc = ";".join(fc_parts)

    cmd = [FF, "-y", *inputs, "-filter_complex", fc, "-map", "[out]",
           "-c:a", "aac", "-b:a", "192k", str(output_path)]
    _run(cmd)


# ── hold (extend last frame) ────────────────────────────────────────────────

def hold(input_path, output_path, extra):
    if extra > 3.0:
        raise SystemExit(
            f"hold extension {extra}s exceeds 3s safety bound. "
            f"Re-record visual instead."
        )
    cmd = [FF, "-y", "-i", str(input_path),
           "-vf", f"tpad=stop_mode=clone:stop_duration={extra}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", str(output_path)]
    _run(cmd)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("atempo")
    a.add_argument("--input", required=True)
    a.add_argument("--output", required=True)
    a.add_argument("--rate", type=float, required=True)
    a.add_argument("--start", type=float)
    a.add_argument("--end", type=float)

    s = sub.add_parser("splice")
    s.add_argument("--input", required=True)
    s.add_argument("--patch", required=True)
    s.add_argument("--output", required=True)
    s.add_argument("--start", type=float, required=True)
    s.add_argument("--end", type=float, required=True)

    t = sub.add_parser("trim_silence")
    t.add_argument("--input", required=True)
    t.add_argument("--output", required=True)
    t.add_argument("--max-pause", type=float, default=2.0)
    t.add_argument("--target-pause", type=float, default=0.6)

    h = sub.add_parser("hold")
    h.add_argument("--input", required=True)
    h.add_argument("--output", required=True)
    h.add_argument("--extra", type=float, required=True)

    args = ap.parse_args()
    if args.cmd == "atempo":
        atempo(args.input, args.output, args.rate, args.start, args.end)
    elif args.cmd == "splice":
        splice(args.input, args.patch, args.output, args.start, args.end)
    elif args.cmd == "trim_silence":
        trim_silence(args.input, args.output, args.max_pause, args.target_pause)
    elif args.cmd == "hold":
        hold(args.input, args.output, args.extra)
    print(f"  → {args.output}")


if __name__ == "__main__":
    main()
