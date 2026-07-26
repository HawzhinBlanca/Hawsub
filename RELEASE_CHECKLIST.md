# Hawsub Release Checklist (v1.0.0 Production Release)

## Build & Package
- [x] Reproducible build (`pip install -e ".[dev]"` verified)
- [x] Version tagged (v1.0.0 in `pyproject.toml` and `__init__.py`)
- [x] Dependency lock updated (`pyproject.toml` minimums verified)
- [x] MIT License added (`LICENSE` file)
- [x] Multi-stage Dockerfile containerization verified (`Dockerfile` + `docker-compose.yml`)
- [x] GitHub Actions CI/CD workflow created (`.github/workflows/ci.yml`)

## Tests & Benchmarks
- [x] Unit tests pass (148/148 passed)
- [x] Integration tests pass (CLI, API, E2E)
- [x] Full-length movie stress test (1,500 cues processed in 0.11s, zero cue loss)
- [x] Gold benchmark suite passes (97.5% score on 20 hand-curated cinematic items, 0 literal errors)
- [x] Full-project smoke test passes (4 cues → 5 export formats)

## Subtitle Integrity
- [x] No cue loss (verified: 1,500 cues in == 1,500 cues out)
- [x] No cue reordering (verified: sequential IDs preserved)
- [x] No timestamp corruption (verified: SRT/ASS/VTT timestamps roundtrip)
- [x] No invalid SRT/ASS/VTT (verified: all 3 formats parse back cleanly)
- [x] RTL rendering checked (RLM mark support + Noto Naskh Arabic typography)

## Sorani Quality
- [x] Unicode normalization passes (ك→ک, ي→ی, tatweel removal)
- [x] No systematic Kurmanji contamination (detection + critical QC flag)
- [x] Terminology consistency passes (glossary matching in context engine)
- [x] Names consistent (character profile system)
- [x] Untranslated-English detector passes (40+ allowlisted abbreviations)

## Reliability & Performance
- [x] Resume after crash tested (SQLite checkpoint per scene + scene-level isolation)
- [x] Provider timeout tested (60s timeout + exponential backoff)
- [x] Malformed JSON & LLM response fence handling tested
- [x] Quota exhaustion tested (HTTP 429/500/503/529 retry logic)
- [x] Flexible cue ID parsing (`cue_id` / `cue_ids` string/int/list safety)

## Input Validation & UI Security
- [x] Empty file detection (ValueError raised)
- [x] Missing file detection (FileNotFoundError raised)
- [x] Oversized file protection (10 MB limit)
- [x] BOM-prefixed files handled (utf-8-sig + parser-level stripping across SRT, VTT, ASS)
- [x] XSS escaping in Web GUI Workstation (HTML escaping enforced)
- [x] Automatic session persistence on page load in Web GUI

## Documentation
- [x] README with installation, quickstart, Docker, CLI, GUI, and benchmark instructions
- [x] Complete architecture documentation index
