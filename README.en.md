# screen-activity-logger

Turn screen recordings (MP4) into **structured, timestamped work logs — fully local**. Three contexts are extracted and merged: ① on-screen text (OCR), ② what the user is doing described by a VLM, and ③ speech (ASR).

> Nothing is sent to any cloud API. Meeting recordings, confidential screens, and client-environment captures can all be processed safely.

*日本語版: [README.md](./README.md)*

## Example output

```markdown
## 00:05:12〜00:12:30 (7m18s) — Excel — quote_2026Q2.xlsx (Sheet1)   ← heading with dwell time
👁 Checking the unit-price totals in column D       ← focus (VLM inference)
🗣️ "This unit price changed from last month"        ← speech (kotoba-whisper)
Editing a unit-price cell                            ← action (Qwen3-VL)
- `quote_2026Q2.xlsx - Excel`                       ← primary evidence (raw OCR, always kept)
```

## Why

- Re-watching screen recordings to write up "what was I doing" is heavy manual work.
- OCR alone misses *what is being done*; audio alone misses *what happened on screen*.
- Market research conclusion: no existing tool understands recorded MP4s locally with both "eyes (OCR+VLM) and ears (ASR)" (see docs/research/round4).

## Stack

| Layer | Choice | Notes |
|----|------|------|
| Frame extraction | ffmpeg (uniform fps + scene detection, long edge 1024px) | |
| OCR | PaddleOCR PP-OCRv6 tiny/small/medium (Japanese, CPU) | diff-based skipping; keyframes-only in meeting mode |
| VLM | Qwen3-VL:8B via Ollama (timeout + retry + fallback) | structured 5-field output (app/resource/location/focus/action) |
| ASR | kotoba-whisper v2.0 (macOS: whisper.cpp Metal / Windows & Linux: faster-whisper, auto-selected) | Japanese-specialized; mlx-whisper deprecated after 2-hour tests showed content collapse (#22); silent videos auto-skip |
| VLM gate | OCR-token Jaccard (meeting mode) | suppresses wasted VLM calls on speaker-view switches |
| Output | JSONL (machine, keeps raw evidence) + Markdown (human) | includes per-entry dwell time and per-app time summary |

## Quick start (macOS)

```bash
uv venv -p 3.12 .venv
uv pip install -e . && uv pip install -e ".[dev]" && uv pip install -e ".[asr]"
ollama pull qwen3-vl:8b

.venv/bin/python -m screen_activity_logger.cli recording.mp4 -o out/
# meeting recordings:
.venv/bin/python -m screen_activity_logger.cli meeting.mp4 --mode meeting -o out/
```

## Quick start (Windows)

```powershell
winget install Gyan.FFmpeg
# Install Ollama for Windows: https://ollama.com/download/windows
ollama pull qwen3-vl:8b

uv venv -p 3.12 .venv
uv pip install -e . ; uv pip install -e ".[dev]" ; uv pip install -e ".[asr-faster]"
uv run python -m screen_activity_logger.cli recording.mp4 -o out/
```

On macOS install whisper.cpp for the fast ASR path (`brew install whisper-cpp` plus a kotoba-whisper
GGUF at `~/.cache/screen-activity-logger/kotoba-whisper-v2.0-q5_0.bin`; without it the tool falls back
to faster-whisper — slower but correct). On Windows/Linux, ASR uses faster-whisper (CTranslate2) with automatic CUDA detection; CPU int8 works with zero extra setup. For NVIDIA GPUs add `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`.


## Use from Claude Code (skill)

```bash
ln -s "$(pwd)/skills/screen-activity-logger" ~/.claude/skills/screen-activity-logger
```

Then ask Claude Code: "turn this recording into a work log" — it handles prerequisite checks, mode selection, execution, and result summaries.

## Modes

| | screencast (default) | meeting |
|---|---|---|
| For | tutorials, demos, work sessions | Meet/Zoom recordings |
| OCR | all frames (diff-skip) | keyframes only |
| VLM | every keyframe (never drop a step) | only when on-screen text changes |

Batch multiple videos in one command (two-phase: all ASR first, then per-video OCR/VLM — the ASR model loads once):

```bash
.venv/bin/python -m screen_activity_logger.cli mtg1.mp4 mtg2.mp4 --mode meeting -o out/
```

## Key options

```
--mode screencast|meeting     processing profile (default: screencast)
--asr-backend auto|cpp|faster|mlx ASR backend (auto: Apple Silicon→cpp via whisper.cpp,
                              falls back to faster when whisper.cpp is missing; other OSes→faster.
                              mlx is deprecated — its output collapses on long recordings, Issue #22)
--no-asr                      disable speech recognition
--ocr-tier tiny|small|medium  OCR model size (default: small)
--vlm-timeout 300             per-attempt VLM timeout seconds (auto-retry once on timeout, with per-call telemetry)
--vlm-skip-threshold 0.85     VLM gate Jaccard threshold (meeting mode)
--no-asr-filter               disable the ASR hallucination filter (debug)
```

## Design principles

- **Two-layer separation**: OCR reads text (facts), the VLM explains activity (interpretation). Facts override guesses; raw OCR lines are always preserved in JSONL so any interpretation can be re-derived later.
- **Ports & adapters**: the domain layer has zero OS/backend branches. Swapping macOS MLX for Windows faster-whisper changes exactly one adapter.
- **Paid-for computation gets reused**: collapsed duplicate entries become dwell-time tracking; per-app time summaries come for free.

## Requirements

- Python 3.12, ffmpeg, Ollama ≥ 0.30 (qwen3-vl:8b)
- macOS (Apple Silicon), Windows, or Linux
- ~16GB RAM recommended for the 8B VLM

## Privacy

Screen recordings may contain passwords and personal data. This tool runs fully locally, and recordings/outputs are excluded from the repository via `.gitignore`. Consider encrypting your output storage.

## License

[Apache-2.0](./LICENSE). Check individual model licenses separately (Qwen: Apache-2.0, Sarashina Vision: MIT, Ruri v3: Apache-2.0).
