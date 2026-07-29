# Hawsub Technical Architecture

## 1. Architectural style

Use a modular pipeline with explicit stage boundaries and typed data contracts.

Each stage should be:
- independently testable;
- resumable;
- idempotent;
- observable;
- replaceable where appropriate.

Avoid giant orchestration classes.

---

## 2. Suggested layers

```text
UI / CLI
   ↓
Application / Workflow Orchestrator
   ↓
Domain Services
   ├─ Source Resolution
   ├─ Context
   ├─ Semantic Translation
   ├─ Sorani Normalization
   ├─ Subtitle Adaptation
   ├─ QC
   └─ Review
   ↓
Provider Adapters
   ├─ Gemini
   ├─ OpenAI
   ├─ Anthropic
   ├─ OpenRouter
   └─ Local OpenAI-compatible
   ↓
Infrastructure
   ├─ FFmpeg
   ├─ ASR
   ├─ Filesystem
   ├─ Project DB
   ├─ Cache
   └─ Logging
```

---

## 3. Module boundaries

### `core/ingest`
- create project;
- register media;
- hash files;
- inspect metadata.

### `core/source_resolver`
- scan embedded/sidecar subtitle sources;
- rank candidates;
- detect language/track type;
- preserve provenance.

### `core/asr`
- local faster-whisper adapter;
- future cloud ASR adapters;
- alignment-only mode;
- anomaly detection mode.

### `core/context`
- Movie/Series/Season/Episode Bible;
- character graph;
- glossary;
- scene summaries.

### `core/scene`
- semantic chunking;
- scene boundaries;
- neighboring-context packaging.

### `core/semantic`
- semantic interpretation contract;
- ambiguity handling;
- foreign-dialogue reasoning.

### `core/translation`
- provider-neutral translation service;
- structured output parsing;
- retries;
- translation memory.

### `core/normalization`
- Sorani Unicode normalization;
- punctuation;
- typography;
- RTL handling.

### `core/adaptation`
- CPS/CPL;
- line breaking;
- resegmentation;
- selective retiming.

### `core/qc`
- semantic checks;
- linguistic checks;
- technical checks;
- confidence scoring;
- second-model verification.

### `core/cost`
- token budget tracking;
- per-model pricing rates;
- cost estimation (`hawsub estimate`);
- expenditure enforcement.

### `core/review`
- issue queue;
- reviewer decisions;
- alternatives;
- feedback store (`hawsub feedback`);
- training data export.

### `core/export`
- SRT;
- ASS;
- VTT;
- QC report;
- project package.

---

## 4. Orchestration

Each workflow step writes a durable status.

Example:

```text
INGEST              complete
SOURCE_RESOLVE      complete
SOURCE_VERIFY       complete
CONTEXT_BUILD       complete
SCENE_001           complete
SCENE_002           complete
SCENE_003           failed
```

Restart from the failed stage, not from the beginning.

---

## 5. Provider interfaces

Recommended abstractions:

```python
class SemanticModel:
    def analyze_scene(self, request): ...
    def translate_scene(self, request): ...
    def verify_translation(self, request): ...
    def analyze_audio(self, request): ...
```

Provider-specific code stays inside adapters.

No business logic should contain hardcoded `if provider == ...` branches except in dependency wiring.

---

## 6. Data persistence

Recommended:
- SQLite for local project metadata in v1;
- project files remain portable;
- JSON artifacts for human-readable stage outputs;
- content-addressed cache for model responses and extracted audio clips.

Potential later upgrade:
- PostgreSQL for team/server deployment.

---

## 7. LLM call boundary

The LLM receives:
- source text;
- context subset;
- glossary subset;
- optional audio clip;
- prompt version.

It does not receive:
- SRT numbering responsibilities;
- final timing ownership;
- raw project state.

The LLM returns structured data only.

---

## 8. Cache key

Suggested cache key:

```text
sha256(
  provider +
  model +
  prompt_version +
  source_text +
  context_hash +
  glossary_hash +
  config_hash
)
```

---

## 9. Failure isolation

A malformed response for one scene must not invalidate the full movie.

Each scene/batch is independently retryable.

---

## 10. External editor integration

Hawsub exports:
- clean subtitle file;
- QC report;
- optional issue markers;
- project metadata.

Subtitle Edit remains the final professional workstation.

---

## 11. Repository structure

```text
Hawsub/
  app/
    ui/
    cli/
  core/
    ingest/
    media/
    source_resolver/
    asr/
    context/
    scene/
    semantic/
    translation/
    normalization/
    adaptation/
    qc/
    review/
    export/
  providers/
    google/
    openai/
    anthropic/
    openrouter/
    local/
  prompts/
  config/
  tests/
    unit/
    integration/
    regression/
    gold/
  docs/
  ADR/
```

Adapt this to the pyVideoTrans repository rather than forcing a rewrite.
