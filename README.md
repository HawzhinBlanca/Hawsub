# Hawsub

**Hawsub** is a production-oriented English → Central Kurdish (Sorani, `ckb`) cinematic subtitle localization system.

Its purpose is not generic machine translation. It is designed to produce high-quality Sorani subtitles for Hollywood films and English-language TV/streaming series by combining:

- transcript-first ingest;
- English audio verification only where needed;
- scene-level context;
- meaning-first semantic translation;
- Sorani orthographic normalization;
- subtitle-specific adaptation and QC;
- exception-based human review.

## Installation

```bash
# Clone the repository
git clone <repo-url> && cd Hawsub

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install in development mode
pip install -e ".[dev]"

# (Optional) Install ASR support
pip install -e ".[asr]"
```

### Requirements

- Python ≥ 3.10
- FFmpeg / FFprobe (for media handling)
- At least one LLM API key (Google, OpenAI, Anthropic, or OpenRouter)

### Environment Setup

Copy the example `.env` file and add your API key(s):

```bash
cp .env.example .env
# Edit .env and add: GOOGLE_API_KEY=your-key-here
```

## Quick Start

### CLI — Process, Inspect & Benchmark

```bash
# Full pipeline: English SRT → Sorani localized SRT/ASS/VTT + QC report
hawsub process -i movie.en.srt -p my_film -o output/

# Inspect subtitle statistics (cue count, duration, word count, reading speed)
hawsub inspect -i movie.en.srt

# Normalize Sorani text to canonical Central Kurdish orthography
hawsub normalize -t "سڵاو كوردستان"

# Run gold benchmark evaluation suite
hawsub benchmark --provider mock --model gemini-2.5-pro
```

### GUI — Interactive Workstation

```bash
hawsub gui --port 8080
# Open http://127.0.0.1:8080 in your browser
```

**GUI Keyboard Shortcuts**:
- `Cmd + S` / `Ctrl + S`: Save cue edit
- `Cmd + Enter` / `Ctrl + Enter`: Accept cue & advance
- `Alt + Right` / `Alt + Left`: Next / Previous cue

### Key System Engines

- **SubtitleSyncEngine**: Timestamp offset shift, framerate conversion (23.976 → 25 fps), and 2-point linear regression drift correction.
- **TranslationDiffEngine**: Word Error Rate (WER) and Character Error Rate (CER) calculation with inline HTML diffs between model output and human edits.
- **SoraniCulturalComplianceEngine**: Cultural sensitivity and broadcast safety audit engine for Central Kurdish media standards.
- **TranslationEnsembleEngine**: Dual-model semantic consensus verification across primary and secondary LLMs.

### Output Files

Each pipeline run produces 5 files:

| File | Format | Description |
|------|--------|-------------|
| `*.ckb.srt` | SubRip | Standard Sorani subtitle file |
| `*.ckb.ass` | Advanced SSA | Styled subtitle file with custom Kurdish fonts |
| `*.ckb.vtt` | WebVTT | Web-compatible subtitle file |
| `*.bilingual.html` | HTML | Side-by-side English/Sorani debug inspector |
| `*.qc_report.json` | JSON | QC audit with confidence scores and issues |

## Configuration

Default config is at `config/hawsub.yaml`. Override with:

```bash
hawsub process -i input.srt -c custom-config.yaml
```

Key settings:
- **Provider**: `google`, `openai`, `anthropic`, `openrouter`, `local`, `mock`
- **Model**: `gemini-2.5-pro`, `gpt-4o`, `claude-sonnet-4-20250514`, etc.
- **QC Profile**: CPS, CPL, line count, duration, and gap thresholds

## Core Strategy

1. Prefer existing professional English subtitles/transcripts.
2. Preserve source timing whenever valid.
3. Use English ASR only as a fallback or verifier.
4. Build movie/episode/series context before translating.
5. Translate meaning, not words.
6. Keep LLMs away from deterministic subtitle structure.
7. Normalize Sorani orthography in code.
8. Retiming/resegmentation happens only when readability requires it.
9. Route uncertainty to a second model or human reviewer.
10. Benchmark every model change on an expert-scored English → Sorani cinematic test set.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run only unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/ --cov=hawsub --cov-report=term-missing
```

**Current status**: 140 tests passing, 96.7% benchmark score.

## Important Model Policy

> The semantic model must be configurable. No production logic may depend directly on one vendor/model.

## Documentation

| Document | Description |
|----------|-------------|
| `BLUEPRINT.md` | Full product blueprint |
| `ARCHITECTURE.md` | Technical architecture and module boundaries |
| `DATA_MODEL.md` | Project entities and schemas |
| `SORANI_STYLE_GUIDE.md` | Language and orthographic standards |
| `CONFIG_SPEC.md` | Runtime configuration schema |
| `QA_SPEC.md` | Quality gates and acceptance criteria |
| `BENCHMARK_SPEC.md` | Expert evaluation framework |
| `RELEASE_CHECKLIST.md` | Production release definition of done |
| `DEV_SETUP.md` | Repository and development setup |
| `PROMPTS.md` | Prompt contracts |

## License

All rights reserved. See LICENSE for details.
