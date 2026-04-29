# pitch-video

> A Claude Code plugin that turns a working prototype + your own voice into a polished pitch video. Slides, demo capture, and voice sync — all built around your audio, never the other way around.

## What this is

A 7-gate workflow for producing a 2–4 minute pitch video, end to end:

1. **Alignment interview** → captures audience, length, tone, must-hits, must-avoids
2. **Script + slide copy** → drafted together, reviewed in one doc
3. **Slide deck** → rendered via the [`frontend-design`](https://github.com/anthropics/claude-plugins) skill
4. **You record voiceover** → in QuickTime, ~3 minutes, one take
5. **Visuals sized to your audio** → slides timed to your pace, prototype demo recorded to fit your demo narration window exactly
6. **Final video assembled** → mp4, ready to submit
7. **Alignment-fix loop** → detects mismatched sections and offers per-region fixes (re-record, atempo, hold longer, trim silence)

## Why this design

The single biggest failure mode in AI-assisted pitch videos is generating visuals before the audio exists. Every TTS voice sounds slightly off; every speaker has their own pace. If the video is locked first and the audio gets recorded to "match," nothing lines up.

This skill flips that. **Your recorded voice is the timing clock.** Slides, prototype demo, transitions — all sized to your actual audio after the fact, using a [Whisper](https://github.com/SYSTRAN/faster-whisper) transcript to find exact section boundaries.

## Installation

> **Requires Claude Code** (CLI or desktop developer app). This plugin runs local tooling — Playwright, ffmpeg, Whisper — and won't work in Claude.ai or the Claude Desktop consumer chat app.

From any Claude Code session, run:

```
/plugin marketplace add Joyceqx/pitch-video
/plugin install pitch-video@pitch-video
/reload-plugins
```

That's it. The plugin appears in `/plugin` → Installed and the skill is invokable as `/pitch-video:pitch-video`.

### Local development install

If you've cloned the repo and want to point Claude Code at your local copy:

```bash
claude --plugin-dir /path/to/pitch-video/plugins/pitch-video
```

### Activate

Once installed, just describe what you want in any Claude Code session:

```
> Make a 3-minute pitch video for my prototype at https://example.com
```

The skill auto-activates on phrases like *"make a pitch video"*, *"showcase submission video"*, *"turn this into a 3-minute demo"*. To invoke it explicitly:

```
/pitch-video:pitch-video
```

### Manual / as a reference

Even without the plugin, the scripts under `skills/pitch-video/scripts/` are runnable on their own:

```bash
# transcribe an audio file
python skills/pitch-video/scripts/transcribe.py voiceover.m4a > transcript.json

# capture slides from any HTML deck
python skills/pitch-video/scripts/capture_slides.py --deck deck.html --output slides/

# record a prototype walk-through (Playwright headless)
python skills/pitch-video/scripts/record_demo.py --url https://example.com --duration 45

# stitch a final video
bash skills/pitch-video/scripts/build_video.sh --transcript transcript.json --audio voiceover.m4a ...
```

## Tooling prerequisites

The skill checks these at gate 0 and offers to install. You don't need them up front.

- Python 3.9+
- `ffmpeg` (via the `imageio-ffmpeg` pip package, no system install needed)
- `playwright` + Chromium browser
- `faster-whisper` (lightweight; runs CPU-only fine)
- `python-docx` (only if you also want a submission .docx)

A clean isolated install fits in a venv:

```bash
python3 -m venv ~/.venv-pitch
source ~/.venv-pitch/bin/activate
pip install playwright imageio-ffmpeg faster-whisper python-docx
playwright install chromium
```

## What the user does manually

Just one thing: **record the voiceover.** The skill writes a SCRIPT.md, you open QuickTime, read it through, save the m4a to your working directory, and reply "audio ready." Everything else is automated.

## What gets written to your working directory

```
your-project/
├── AGENDA.md                  # gate 1 — alignment + must-hits
├── SCRIPT.md                  # gate 2 — script + slide copy + cue card
├── presentation/index.html    # gate 3 — the deck
├── prototype_reference.webm   # gate 3 — optional watch-along
├── voiceover.m4a              # gate 4 — your recording
├── transcript.json            # gate 5 — Whisper transcript with section timestamps
├── slides/                    # gate 5 — captured PNGs
├── prototype/prototype.webm   # gate 5 — final demo recording
└── output/pitch_video.mp4     # gate 6 — done
```

## Safety bounds

The skill won't apply auto-fixes that degrade quality:

- `atempo` (audio speed): 0.92×–1.18× safe, 1.18×–1.25× noticeable but acceptable, beyond → requires re-record.
- Slide hold extension: max +3 seconds.
- Silence trimming: collapses pauses > 2s down to 0.6s, never strips all silence.

## Stage-gate philosophy

Each gate has explicit user approval. Hitting a wall at gate 6 because the script was wrong at gate 2 wastes hours. The chat caps at:
- 3 rounds at gate 1 (alignment)
- 2 rounds at gate 2 (script)

After that, the skill writes everything to a file and the user edits it directly. No endless chat loops.

## Known limitations

- **Auth-walled prototypes**: the Playwright capture won't work behind a login. Workaround: record your own demo with QuickTime and drop the .mov in the working directory.
- **Voice cloning / TTS**: not supported. The skill is built around the assumption that the user reads their own script. Add it yourself if you need it, but be warned: TTS still sounds off on technical terms like "cosine similarity" and "objective function."
- **Multilingual**: only tested with English audio + English Whisper model. Other languages should work — pass `--language` to `transcribe.py`.
- **Long videos**: tested for 2–4 minute videos. Longer pitches (10+ min) probably want a different tool.

## License

MIT — see LICENSE.

## Contributing

PRs welcome. Particularly interested in:
- Better misalignment detection heuristics
- Live-render slide deck (currently re-screenshots PNGs)
- Audio cleanup (denoise, normalize loudness)
- More slide aesthetic templates

## Acknowledgments

Built during OIT 277 (Stanford GSB, Spring 2026) while making a 3-minute pitch video for the [IndiStream](https://indistream.vercel.app/) artist marketplace prototype. Every gate in this workflow exists because we hit the corresponding failure mode at least twice while making that video.
