#!/usr/bin/env python3
"""Detect audio/visual misalignment regions in a built pitch video.

Reads:
  - transcript.json    (output of transcribe.py)
  - timing.json        (slide → expected audio segment, written by build_video.sh)

Outputs JSON to stdout: a list of regions where the actual audio section
is more than --threshold seconds longer or shorter than its slide visual.

Usage:
  python detect_misalignment.py --transcript transcript.json --timing timing.json
  python detect_misalignment.py --transcript transcript.json --timing timing.json --threshold 1.5
"""
import argparse
import json
import sys
from pathlib import Path


def detect(transcript: dict, timing: dict, threshold: float = 1.5):
    """Return a list of misaligned regions.

    `timing` schema:
      {
        "slides": [
          {"name": "slide_02", "video_start": 3.0, "video_end": 42.9,
           "trigger_phrase": "Quick scenario"},
          ...
        ],
        "demo": {"video_start": 57.8, "video_end": 94.7,
                 "trigger_phrase": "Let me show you"}
      }
    """
    triggers = transcript.get("trigger_phrases", {})
    regions = []

    slides = timing.get("slides", [])
    for i, slide in enumerate(slides):
        phrase = slide.get("trigger_phrase")
        if not phrase or phrase not in triggers or triggers[phrase] is None:
            continue
        audio_start = triggers[phrase]
        # audio_end is the next slide's start, or the audio total duration
        next_phrase = slides[i + 1].get("trigger_phrase") if i + 1 < len(slides) else None
        if next_phrase and triggers.get(next_phrase) is not None:
            audio_end = triggers[next_phrase]
        else:
            audio_end = transcript["duration"]
        audio_dur = audio_end - audio_start
        video_dur = slide["video_end"] - slide["video_start"]

        diff = audio_dur - video_dur
        if abs(diff) > threshold:
            regions.append({
                "slide": slide["name"],
                "audio_start": round(audio_start, 2),
                "audio_end": round(audio_end, 2),
                "audio_duration": round(audio_dur, 2),
                "video_duration": round(video_dur, 2),
                "drift": round(diff, 2),
                "diagnosis": (
                    "audio longer than visual" if diff > 0
                    else "audio shorter than visual"
                ),
                "suggested_fixes": _suggest_fixes(diff, audio_dur, video_dur),
            })

    return regions


def _suggest_fixes(drift, audio_dur, video_dur):
    """Suggest fix options based on drift magnitude and direction."""
    suggestions = []
    if drift > 0:
        # audio runs longer than visual
        rate = audio_dur / video_dur
        if rate <= 1.18:
            suggestions.append(f"speed audio with atempo={round(rate, 3)} (safe)")
        elif rate <= 1.25:
            suggestions.append(f"speed audio with atempo={round(rate, 3)} (noticeable but ok)")
        else:
            suggestions.append("re-record this section (atempo would exceed safe range)")
        if drift <= 3.0:
            suggestions.append(f"or extend visual hold by {round(drift, 1)}s")
    else:
        # audio shorter than visual
        rate = audio_dur / video_dur
        if rate >= 0.92:
            suggestions.append(f"slow audio with atempo={round(rate, 3)} (safe)")
        elif rate >= 0.85:
            suggestions.append(f"slow audio with atempo={round(rate, 3)} (noticeable)")
        else:
            suggestions.append("re-record this section (atempo would exceed safe range)")
        suggestions.append("or trim visual to match audio length")
    return suggestions


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--timing", required=True)
    ap.add_argument("--threshold", type=float, default=1.5,
                    help="seconds of drift to flag (default 1.5)")
    args = ap.parse_args()

    transcript = json.loads(Path(args.transcript).read_text())
    timing = json.loads(Path(args.timing).read_text())

    regions = detect(transcript, timing, args.threshold)
    print(json.dumps(regions, indent=2))

    if regions:
        print(f"\n  {len(regions)} misaligned region(s) found "
              f"(threshold {args.threshold}s)", file=sys.stderr)
    else:
        print(f"\n  no misalignment > {args.threshold}s — looks aligned",
              file=sys.stderr)


if __name__ == "__main__":
    main()
