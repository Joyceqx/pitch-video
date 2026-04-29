---
name: pitch-video
description: Use when the user has a working prototype and pitch requirements (e.g. "make a 3-min pitch video", "showcase submission video", "investor demo", "turn this into a demo reel"). Orchestrates a 7-gate workflow — alignment interview → script + slide deck → user records their own voiceover → final video assembly with auto-alignment fixes. The user's voice is the timing source of truth; visuals are sized to it.
license: Complete terms in LICENSE
---

This skill produces a polished pitch video from (a) a working prototype the user can demo and (b) a script the user reads themselves. The user's recorded voice is the timing clock — every visual is sized to it. Never build the video before the audio exists.

## What you produce, in order

1. **AGENDA.md** — alignment doc (gate 1)
2. **SCRIPT.md** — spoken script + slide copy + demo cue card (gate 2)
3. **presentation/index.html** — the slide deck (gate 3, via `frontend-design`)
4. **prototype_reference.webm** — optional silent prototype walk-through for the user to watch while practicing (gate 3, only on request)
5. **voiceover.m4a** — the user records this themselves (gate 4)
6. **transcript.json** + sized visual capture (gate 5)
7. **output/pitch_video.mp4** — final video (gate 6)

## The 7-gate workflow

Move through gates IN ORDER. Don't skip. Each gate ends with explicit user approval (except gates 0 and 5).

### Gate 0: Tooling check
Run `bash ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/check_tooling.sh`.

If anything's missing, the script prints the install commands. **Ask the user before running them** — never auto-install.

Required: `python3`, `ffmpeg` (via the `imageio-ffmpeg` pip package or system), `playwright` + chromium browser, `faster-whisper`, `python-docx` (only if a submission .docx is also requested).

The script suggests a venv at `~/.venv-pitch/` to keep installs isolated.

### Gate 1: Alignment interview → AGENDA.md

Ask the user the following — but **cap chat at 3 rounds of clarification**. After the third round, write everything to `AGENDA.md` in the user's working directory and tell the user to edit it directly. Do not keep iterating in chat.

What to ask (in this order):

1. **Pitch context** — audience, format (live / video submission), length budget, stakes (class / investor / demo day).
2. **Style** — pick one: *professional · casual · academic · sales-y*. Give a one-line example for each.
3. **Tone constraints** — em-dashes ok? jargon level? humor? technical depth?
4. **Three things they MUST hit** and **three to avoid**.
5. **Prototype URL + the demo flow** — what page to land on, what to type, what to click. Concrete sequence.
6. **Existing assets** — proposal docs, brand colors, deck templates, prior pitches.
7. **Reference prototype footage?** Yes/no. Some users like to watch the prototype while recording; others read straight from script.

Use `templates/agenda.md` as the AGENDA.md skeleton. Fill it in from the chat.

After the file is written, send it to the user for approval. If they want changes, edit the file (don't restart the chat).

### Gate 2: Script + slide copy together

Generate `SCRIPT.md` containing both the spoken script AND the slide-by-slide copy. They live together in one doc so the user can see the script and the slide that goes with it side by side.

Format per section:

```markdown
## Section 1: Problem  ·  ~38s

### Spoken script
> "Quick scenario..."

### Slide copy
- **Slide 2 — The Problem**
- Eyebrow: 01 · The market is broken on both ends
- Two columns: "Buyers settle." / "Artists stay invisible."
- Body: <text>
```

Word-budget the script: aim for 130–150 wpm at the user's stated length. Show a word-count and time-estimate per section.

If the demo segment exists, include the demo cue card in this same doc — what to click, what to say while clicking.

**Send to user. Wait for approval.** This is the biggest taste gate. Iterate ONE more time if asked. After two rounds, ask the user to edit SCRIPT.md directly.

### Gate 3: Slide deck rendered

Invoke the `frontend-design` skill (or `frontend-design:frontend-design` if that variant is available) with:
- The slide copy from SCRIPT.md
- The aesthetic guidance from AGENDA.md (style, tone)
- A constraint that the deck must work as a 1920×1080 single-file HTML with keyboard navigation (arrow keys advance slides)

Output: `presentation/index.html`. Open it in the browser for the user to review.

**If reference footage was requested at gate 1**, also run:
```
python ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/record_demo.py \
  --url <prototype-url> \
  --flow <flow-name> \
  --duration 60 \
  --output prototype_reference.webm
```

That gives the user a generous (~60s) silent walk-through of the prototype to watch while practicing. It's not the final demo recording — that comes at gate 5, sized to the actual audio.

User approves the deck (look + copy).

### Gate 4: User records voiceover

Tell the user, verbatim:

> Open QuickTime → File → New Audio Recording. Read SCRIPT.md straight through, including any demo narration. Pause briefly between sections (~0.6s) so I can detect transitions. Save as `voiceover.m4a` in this working directory. Reply "audio ready" when done.

Wait. Do not generate the video until the file exists.

### Gate 5: Sized visual capture

Once `voiceover.m4a` exists:

1. Transcribe with timestamps:
   ```
   python ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/transcribe.py voiceover.m4a > transcript.json
   ```
2. Detect section boundaries by matching trigger phrases from SCRIPT.md against the transcript. Compute exact section durations.
3. Capture slides as PNGs:
   ```
   python ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/capture_slides.py \
     --deck presentation/index.html \
     --output slides/
   ```
4. Record the prototype demo, **sized to the demo-narration window from the transcript**:
   ```
   python ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/record_demo.py \
     --url <prototype-url> \
     --flow <flow-name> \
     --duration <demo-narration-seconds-from-transcript> \
     --output prototype/prototype.webm
   ```
   No time-stretching unless mismatch is < 1.5s.

### Gate 6: Final video assembled

Run:
```
bash ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/build_video.sh \
  --transcript transcript.json \
  --audio voiceover.m4a \
  --slides slides/ \
  --prototype prototype/prototype.webm \
  --output output/pitch_video.mp4
```

Open the file. The first cut should be 80/100 because nothing was guessed — every visual was sized to the audio.

### Gate 7: Alignment-fix loop (only if needed)

Run:
```
python ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/detect_misalignment.py \
  --transcript transcript.json \
  --video output/pitch_video.mp4
```

It returns regions where audio/visual mismatch > 1.5s. For each flagged region, offer the user a fix menu:

| Option | What it does | When to suggest |
|---|---|---|
| (a) Re-record this section | User records just the misaligned chunk; splice via `audio_edit.py --splice` | First choice for "voice sounds rushed" feedback |
| (b) Speed up audio | `atempo` ×1.05–1.18 (safe), 1.18–1.25 (acceptable). Beyond → require re-record. | When audio runs longer than visual |
| (c) Slow audio | `atempo` ×0.92–0.98. Beyond 0.92 → require re-record. | When audio finishes too soon |
| (d) Extend visual hold | Hold slide for up to +3s. Beyond → re-record. | When visual ends but audio still going |
| (e) Trim silence | Collapse pauses > 2.0s to 0.6s. Never strip all silence. | When user paused too long |
| (f) Accept as-is | No-op. | When mismatch is < 1.5s anyway |

Apply fixes via `audio_edit.py`, rebuild via `build_video.sh`. Loop until user accepts.

## Safety bounds (hard-coded — never exceed)

- `atempo` 0.92–1.18 = imperceptible. 1.18–1.25 = noticeable but acceptable. Outside this range → REQUIRE re-record, do not auto-fix.
- Slide hold extension: max +3 seconds. Beyond → re-record.
- Silence trim: collapse pauses > 2.0s to 0.6s. Never remove all silence — kills natural rhythm.
- Whisper transcript drift on punctuation: ±0.3s. Treat as noise, not signal. Don't fight it.

## What you must NOT do

- ❌ Build the final video before the user records audio.
- ❌ Skip the alignment interview at gate 1.
- ❌ Iterate in chat past 3 rounds at gate 1, or 2 rounds at gate 2 — write to a file and let the user edit it.
- ❌ Auto-install tooling without explicit user permission.
- ❌ Time-stretch the prototype by more than 1.25× without warning the user.
- ❌ Use TTS by default. The user reads their own voice — that's the whole design.

## What lives where

```
${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/
├── SKILL.md                           # this file
├── scripts/
│   ├── check_tooling.sh               # gate 0
│   ├── capture_slides.py              # gate 5
│   ├── record_demo.py                 # gates 3 (reference), 5 (final)
│   ├── transcribe.py                  # gate 5
│   ├── detect_misalignment.py         # gate 7
│   ├── audio_edit.py                  # gate 7
│   ├── build_video.sh                 # gate 6
│   └── make_submission_doc.py         # optional companion artifact
└── templates/
    └── agenda.md                       # gate 1 skeleton
```

## A note on the philosophy

The single biggest design choice is: **the user's recorded voice is the source of truth for timing**. Every other artifact (slides, prototype demo, transitions) is sized to that audio after the fact. This sidesteps the failure mode where you build a video to a target pace, the user reads at a different pace, and nothing lines up.

Most rework in pitch-video production comes from generating downstream artifacts (slides, demos, video) from upstream guesses. The gates exist to catch each guess before it propagates.
