# Hawsub Configuration Specification

Example:

```yaml
project:
  target_language: ckb
  mode: professional
  qc_profile: house_standard
  style_guide: sorani-default-v1

source:
  prefer_existing_subtitles: true
  allow_asr_fallback: true
  preserve_source_timing: true

asr:
  local_provider: faster-whisper
  model: large-v3
  use_for_full_transcription_only_if_needed: true
  use_for_verification: true

semantic:
  provider: google
  model: gemini-2.5-pro
  temperature: 0.2

translation:
  provider: google
  model: gemini-2.5-pro
  structured_output: true
  scene_batch_min_cues: 10
  scene_batch_max_cues: 30

verification:
  enabled: true
  provider: configurable
  model: configurable
  trigger_threshold: 0.88
  verify_critical_flags: true

context:
  use_movie_bible: true
  use_series_bible: true
  use_character_profiles: true
  use_glossary: true
  previous_scene_summary: true
  next_scene_hint: true

sorani:
  force_ckb: true
  forbid_kurmanji: true
  unicode_normalization: true
  rtl_normalization: true

qc:
  profile: house_standard
  semantic: true
  linguistic: true
  technical: true

profiles:
  house_standard:
    max_lines: 2
    preferred_cps: 17
    hard_max_cps: 20
    preferred_cpl: 40
    hard_max_cpl: 42
    min_duration_ms: 800
    min_gap_ms: 80

privacy:
  upload_entire_media: false
  upload_only_required_clips: true
  redact_logs: true

cache:
  enabled: true

jobs:
  resumable: true
  checkpoint_per_scene: true
```
