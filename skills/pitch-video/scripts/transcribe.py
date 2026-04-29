#!/usr/bin/env python3
"""Transcribe an audio file with section-level timestamps using faster-whisper.

Output: JSON to stdout (or --output path) shaped as:
  {
    "duration": float,
    "segments": [{"start": float, "end": float, "text": str}, ...],
    "trigger_phrases": {"<phrase>": <timestamp_seconds>, ...}
  }

`trigger_phrases` is populated when --triggers is passed — used by the skill
to find exact section boundaries (e.g. "Here's the deal" → slide 3 starts here).

Usage:
  python transcribe.py voiceover.m4a > transcript.json
  python transcribe.py voiceover.m4a --triggers "Here's the deal,Under the hood" > transcript.json
  python transcribe.py voiceover.m4a --output transcript.json
"""
import argparse
import json
import sys
from pathlib import Path


def transcribe(audio_path: str, model_size: str = "base.en", language: str = "en"):
    from faster_whisper import WhisperModel

    print(f"  loading whisper model ({model_size})...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"  transcribing {audio_path}...", file=sys.stderr)
    segments_iter, info = model.transcribe(
        audio_path,
        word_timestamps=False,
        language=language,
    )

    segments = []
    for seg in segments_iter:
        segments.append({
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
        })

    return {
        "duration": round(info.duration, 3),
        "language": info.language,
        "segments": segments,
    }


def find_triggers(segments, phrases):
    """For each phrase, find the timestamp where it first appears.

    Whisper transcripts often have transcription drift on punctuation and
    proper nouns. We use a fuzzy contains-check (case-insensitive, normalized
    whitespace, only first 3 words of the phrase) to be tolerant.
    """
    found = {}
    for phrase in phrases:
        phrase = phrase.strip()
        if not phrase:
            continue
        # use first 3 words as the search key — robust to whisper drift
        key = " ".join(phrase.lower().split()[:3])
        for seg in segments:
            if key in " ".join(seg["text"].lower().split()):
                found[phrase] = seg["start"]
                break
        if phrase not in found:
            found[phrase] = None  # not found
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("audio", help="audio file (m4a, mp3, mp4, mov, wav, etc.)")
    ap.add_argument("--model", default="base.en",
                    help="whisper model size (tiny.en|base.en|small.en|medium.en)")
    ap.add_argument("--language", default="en")
    ap.add_argument("--triggers",
                    help="comma-separated trigger phrases to locate")
    ap.add_argument("--output", "-o",
                    help="output path for JSON (default: stdout)")
    args = ap.parse_args()

    if not Path(args.audio).exists():
        print(f"error: {args.audio} not found", file=sys.stderr)
        sys.exit(1)

    out = transcribe(args.audio, args.model, args.language)

    if args.triggers:
        phrases = [p.strip() for p in args.triggers.split(",") if p.strip()]
        out["trigger_phrases"] = find_triggers(out["segments"], phrases)

    text = json.dumps(out, indent=2)
    if args.output:
        Path(args.output).write_text(text)
        print(f"  wrote → {args.output}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
