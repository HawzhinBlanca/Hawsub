# Hawsub Data Model

## 1. Core entities

### Project
Represents one movie or one episode localization job.

Fields:
- `id`
- `title`
- `project_type` (`movie`, `episode`)
- `target_language` (`ckb`)
- `status`
- `created_at`
- `updated_at`
- `qc_profile`
- `style_guide_version`
- `semantic_provider`
- `semantic_model`
- `source_media_id`

### MediaAsset
- `id`
- `project_id`
- `path`
- `sha256`
- `duration_ms`
- `container`
- `fps`
- `audio_tracks`
- `subtitle_tracks`

### SubtitleTrack
- `id`
- `project_id`
- `origin` (`embedded`, `sidecar`, `generated`, `manual`)
- `language`
- `format`
- `track_type` (`full`, `forced`, `sdh`, `unknown`)
- `quality_score`
- `selected_as_master`
- `source_path`

### SubtitleCue
- `id`
- `project_id`
- `track_id`
- `sequence`
- `start_ms`
- `end_ms`
- `source_text`
- `speaker`
- `source_confidence`
- `foreign_language`
- `narrative_opacity`
- `scene_id`

### Scene
- `id`
- `project_id`
- `start_ms`
- `end_ms`
- `summary`
- `characters`
- `location`
- `plot_state`
- `previous_scene_id`
- `next_scene_id`

### Character
- `id`
- `project_id`
- `name`
- `aliases`
- `target_name`
- `speech_style`
- `role`
- `relationship_notes`

### GlossaryEntry
- `id`
- `scope` (`global`, `series`, `season`, `project`)
- `source_term`
- `approved_target`
- `notes`
- `case_sensitive`
- `status`

### SemanticInterpretation
- `cue_ids`
- `literal_source`
- `intended_meaning`
- `tone`
- `register`
- `subtext`
- `ambiguity_score`
- `model_run_id`

### TranslationCandidate
- `id`
- `cue_ids`
- `text`
- `provider`
- `model`
- `confidence`
- `is_primary`
- `is_approved`
- `review_notes`

### QCResult
- `id`
- `cue_ids`
- `category` (`semantic`, `linguistic`, `technical`)
- `rule`
- `severity`
- `score`
- `message`
- `status`

### ReviewDecision
- `id`
- `cue_ids`
- `reviewer`
- `action`
- `previous_text`
- `approved_text`
- `notes`
- `created_at`

### ProviderRun
- `id`
- `provider`
- `model`
- `prompt_version`
- `request_hash`
- `input_tokens`
- `output_tokens`
- `latency_ms`
- `cost`
- `status`
- `error`

### Export
- `id`
- `project_id`
- `format`
- `path`
- `sha256`
- `created_at`

---

## 2. Internal subtitle object

Recommended normalized structure:

```json
{
  "cue_id": 431,
  "start_ms": 1284210,
  "end_ms": 1286940,
  "source_text": "You're pushing your luck.",
  "target_text": "...",
  "speaker": null,
  "scene_id": "S034",
  "source_track": "official_en",
  "source_confidence": 0.98,
  "semantic_confidence": 0.95,
  "translation_confidence": 0.96,
  "technical_confidence": 0.98,
  "overall_confidence": 0.96
}
```

---

## 3. Immutability

Preserve:
- original source cue;
- original timing;
- original translation candidate;
- every reviewer change.

Do not overwrite source truth.

---

## 4. Versioning

Every stage should produce a revision:

- source master
- normalized source
- semantic interpretation
- translation v1
- normalization
- adaptation
- QC fixes
- reviewer-approved
- final export

---

## 5. Provenance

Every generated target cue must be traceable to:
- source cue(s);
- model;
- prompt version;
- context package;
- glossary version;
- reviewer action.
