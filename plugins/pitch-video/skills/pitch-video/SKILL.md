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

**How to run this gate:**
1. Open with: *"I'm going to ask you 7 quick questions to align on what we're building. Pick from the options or write your own — there's no wrong answer."*
2. Ask **ONE question per turn**. Wait for the user's answer before moving on. Do not stack questions.
3. For multiple-choice questions, use the `AskUserQuestion` tool when available — it gives the user a clean picker with an "Other" text input for free-form answers.
4. After each answer, summarize back in one line ("Got it: hybrid slides + demo, ~3 min, GSB judges") and move to the next question.
5. **Cap clarification at 3 rounds total** (across all questions combined). After three back-and-forths without progress, write what you have to `AGENDA.md` and tell the user to edit it directly. Do not keep iterating in chat.

The 7 questions, in order:

**Q1. Pitch context** — audience, length budget, stakes.
> Open question. Free-form answer.

**Q2. Video format** — pick one (or describe a custom mix):
- **(a) Slides-only presentation** — narrated slides, no live prototype footage. Best when the prototype isn't visually compelling, or when the message is conceptual.
- **(b) Hybrid (slides + demo)** — slides bookending a live prototype walkthrough. Best for product/showcase pitches. Default for most class submissions.
- **(c) Demo-focused** — voiceover narrating prototype navigation end-to-end, no static slides (or just a title + end card). Best when the product itself tells the story.
- **(d) Custom mix** — user describes their own structure (e.g. "two demo segments separated by a stats slide").

**Q3. Style** — pick one:
- **Professional** — investor-ready, full sentences, clear framing
- **Casual / verbal** — contractions, sentence fragments, conversational
- **Academic** — methodology-forward, technical depth, citations
- **Sales-y** — outcome-driven, value prop hammered, call-to-action close
- *Other / mixed* — user describes

**Q4. Tone constraints** — em-dashes ok? jargon level? humor? technical depth? Free-form, but offer sensible defaults.

**Q5. Three MUST-hits and three to AVOID.** Free-form list.

**Q6. Prototype URL + demo flow** — skip entirely if format is (a) slides-only. Otherwise: what URL to land on, what to type, what to click. Concrete sequence.

**Q7. Reference prototype footage during recording?** — skip if format is (a). Otherwise: yes/no. Separate from the final video format — this is just a rehearsal aid (a silent prototype walkthrough the user watches while reading the script).

Existing assets (proposal docs, brand colors, prior pitches) can be mentioned by the user any time during the interview, or pointed to via paths in `AGENDA.md` after.

Use `templates/agenda.md` as the AGENDA.md skeleton. Fill it in incrementally as answers come in.

After all 7 are answered, write the full `AGENDA.md` and send it to the user for approval. If they want changes, edit the file (don't restart the chat).

### Gate 2: Script + slide copy together

Generate `SCRIPT.md` — the contents adapt to the chosen video format from gate 1:

- **Slides-only (a)**: spoken script + slide-by-slide copy. No demo cue card.
- **Hybrid (b)**: spoken script + slide-by-slide copy + demo cue card (what to click, what to say while clicking).
- **Demo-focused (c)**: spoken script timed to prototype actions (each script line tied to a click/type/scroll beat). No slide copy except optional title + end card.
- **Custom mix (d)**: combine the above per section as the user described.

Format per section (hybrid example):

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

For demo-focused sections, format like:
```markdown
## Section 2: Live walkthrough  ·  ~75s

### Spoken script (timed to prototype actions)
> [0:00–0:08] On landing page: "Here's the buyer side..."
> [0:08–0:25] After typing query: "Watch — results rank live..."
> [0:25–0:40] On work detail: "Every artist verified..."
```

Word-budget the script: aim for 130–150 wpm at the user's stated length. Show a word-count and time-estimate per section.

**Send to user. Wait for approval.** This is the biggest taste gate. Iterate ONE more time if asked. After two rounds, ask the user to edit SCRIPT.md directly.

### Gate 3: Slide deck rendered (format-aware)

Branch on the format chosen at gate 1:

- **Slides-only (a) or Hybrid (b)**: invoke the `frontend-design` skill (or `frontend-design:frontend-design` if available) with the slide copy from SCRIPT.md and aesthetic guidance from AGENDA.md. Constrain the deck to 1920×1080 single-file HTML with keyboard navigation. Output: `presentation/index.html`.
- **Demo-focused (c)**: skip a full deck. If the agenda calls for a title or end card, generate a minimal 1–2 slide HTML at `presentation/index.html` with just those cards.
- **Custom mix (d)**: build only the slides the user actually called for in their structure.

Open whatever was built for the user to review.

**If reference footage was requested at gate 1**, also run:
```
python ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/record_demo.py \
  --url <prototype-url> \
  --flow <flow-name> \
  --duration 60 \
  --output prototype_reference.webm
```

That gives the user a generous (~60s) silent walk-through of the prototype to watch while practicing. It's not the final demo recording — that comes at gate 5, sized to the actual audio.

User approves what was built.

### Gate 4: User records voiceover

Tell the user, verbatim:

> Open QuickTime → File → New Audio Recording. Read SCRIPT.md straight through, including any demo narration. Pause briefly between sections (~0.6s) so I can detect transitions. Save as `voiceover.m4a` in this working directory. Reply "audio ready" when done.

Wait. Do not generate the video until the file exists.

### Gate 5: Sized visual capture (format-aware)

Once `voiceover.m4a` exists:

1. Transcribe with timestamps (always):
   ```
   python ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/transcribe.py voiceover.m4a > transcript.json
   ```
2. Detect section boundaries by matching trigger phrases from SCRIPT.md against the transcript. Compute exact section durations.

Then branch on format:

- **Slides-only (a)**: capture slides only.
  ```
  python ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/capture_slides.py \
    --deck presentation/index.html --output slides/
  ```

- **Hybrid (b)**: capture slides AND record the prototype demo sized to the demo-narration window from the transcript.
  ```
  python ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/capture_slides.py \
    --deck presentation/index.html --output slides/
  python ${CLAUDE_PLUGIN_ROOT}/skills/pitch-video/scripts/record_demo.py \
    --url <prototype-url> --flow <flow-name> \
    --duration <demo-seconds-from-transcript> --output prototype/prototype.webm
  ```

- **Demo-focused (c)**: record one prototype walkthrough sized to the full audio length (minus any title/end cards). Capture title/end card slide(s) if they exist.

- **Custom mix (d)**: capture slides for slide-segments, record one prototype clip per demo-segment, each sized to its own narration window.

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
