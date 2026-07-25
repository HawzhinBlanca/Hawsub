# Hawsub — Full E2E Product Blueprint

## 1. Mission

Build a top-tier professional subtitle localization system specialized for:

> English cinematic dialogue → natural, culturally appropriate, context-aware Central Kurdish / Sorani subtitles.

The system must understand narrative meaning, relationships, tone, sarcasm, humor, plot context, names, terminology, and deliberate ambiguity.

The target is not “good machine translation.” The target is:

> **Natural Sorani written by someone who clearly understood the movie.**

---

## 2. Primary use case

**Input**
- Hollywood films
- English-language TV/streaming episodes
- existing English SRT/ASS/VTT or embedded subtitle tracks when available
- English audio

**Output**
- professional Sorani SRT
- ASS
- VTT
- QC report
- project audit trail

---

## 3. Product principles

### 3.1 Existing subtitles first

Priority order:

1. official/existing English subtitle track
2. high-quality sidecar English subtitles
3. embedded English text subtitle
4. transcript/script
5. English ASR fallback

Do not transcribe clean English audio when a reliable professional source subtitle already exists.

### 3.2 Separate recognition from translation

Recognition and Sorani localization are separate stages.

`English speech → English source text → semantic interpretation → Sorani localization`

### 3.3 Meaning before translation

The translation system must reason through:

`source wording → intended meaning → natural Sorani`

Do not translate idioms word-by-word.

### 3.4 Preserve timing first

English timing is the master anchor unless readability or technical constraints require adaptation.

### 3.5 Deterministic structure

The LLM does not own:
- cue IDs;
- timestamps;
- SRT syntax;
- ASS metadata;
- subtitle numbering;
- Unicode normalization;
- basic QC calculations.

### 3.6 Configurable models

The production semantic model is a provider setting, not architecture.

Initial default may be Gemini 2.5 Pro, but it must be replaceable without refactoring localization logic.

---

## 4. End-to-end flow

```text
MEDIA INPUT
    ↓
FFprobe / source discovery
    ↓
Best existing English subtitle/transcript?
    ├─ yes → use as source master
    └─ no  → English ASR fallback
    ↓
Source validation
    ↓
Flag suspicious / missing / foreign-language segments
    ↓
Movie / Series / Episode context engine
    ↓
Scene segmentation
    ↓
Semantic interpretation
    ↓
Meaning-first English → Sorani translation
    ↓
Sorani normalization
    ↓
Subtitle adaptation
    ↓
Semantic + linguistic + technical QC
    ↓
Second-model verification for uncertain lines only
    ↓
Human review queue
    ↓
Subtitle Edit final pass
    ↓
SRT / ASS / VTT
```

---

## 5. Core open-source strategy

### Reuse from pyVideoTrans

Reuse where practical:
- media loading;
- FFmpeg integration;
- subtitle import/export;
- project handling;
- ASR provider interfaces;
- translation provider interfaces;
- GUI shell;
- CLI;
- batch processing;
- optional dubbing/TTS support.

### Do not rebuild

Do not build:
- a new video player;
- a waveform editor;
- custom media codecs;
- a complete OOONA/EZTitles clone;
- a new FFmpeg;
- Kurdish ASR;
- generic multilingual support in v1.

---

## 6. Custom Hawsub modules

Hawsub's differentiation should be concentrated in five areas:

1. **Source Resolver**
2. **Context Engine**
3. **Semantic Translation Engine**
4. **Sorani Quality Layer**
5. **Confidence / QC Engine**

---

## 7. Source Resolver

Responsibilities:
- inspect media streams;
- identify embedded English tracks;
- scan sidecar files;
- detect forced/SDH tracks;
- rank sources;
- preserve provenance;
- allow manual override.

Never silently replace a source track.

---

## 8. Source validation

Use three tiers.

### Tier 1 — trusted
No extra work for coherent professional subtitle tracks.

### Tier 2 — lightweight anomaly detection
Use local ASR/alignment to find:
- speech without captions;
- large text/audio mismatch;
- likely names;
- timing anomalies;
- foreign-language speech.

### Tier 3 — multimodal arbitration
Only suspicious segments get:
- source subtitle;
- 10–30 sec audio clip;
- neighboring dialogue;
- scene context.

Return structured corrections or uncertainty flags.

---

## 9. Foreign-language dialogue

Support four cases.

### A. English subtitle translates foreign speech
Translate that intended meaning into Sorani.

### B. English subtitle intentionally hides it
Example: `[Speaking Spanish]`
Preserve that narrative opacity.

### C. Dialogue missing unintentionally
Flag.

### D. Intended-to-be-understood dialogue missing
Transcribe/translate as an exception workflow.

Never reveal information the original audience was not meant to understand.

---

## 10. Context engine

Maintain:

### Series Bible
- world rules;
- recurring cast;
- terminology;
- recurring phrases.

### Season Bible
- season-specific plot state;
- relationship changes;
- terminology changes.

### Episode/Movie Bible
- synopsis;
- characters;
- relationships;
- roles;
- locations;
- organizations;
- setting;
- period;
- recurring terms.

### Scene context
- current characters;
- prior scene summary;
- next-scene hint;
- plot state;
- glossary subset.

---

## 11. Translation unit

Do not translate one subtitle at a time.

Do not translate the whole movie in one giant output.

Typical unit:
- 10–30 subtitle cues;
- preferably scene-aligned.

Provide:
- source cues;
- scene summary;
- prior/next context;
- relevant glossary;
- character relations;
- audio only when useful.

---

## 12. Semantic representation

For difficult dialogue, store:

```json
{
  "cue_ids": [431],
  "source": "You're pushing your luck.",
  "meaning": "You are taking increasingly dangerous risks and are being warned to stop.",
  "tone": "warning",
  "register": "informal",
  "subtext": "speaker may retaliate",
  "ambiguity": 0.08
}
```

Easy lines may use a compact representation.

---

## 13. Sorani translation requirements

Target:
- Central Kurdish / Sorani;
- Arabic-based script;
- Iraqi Kurdistan usage;
- no Kurmanji contamination;
- preserve tone;
- preserve implication;
- natural dialogue;
- idiomatic rendering;
- concise enough for subtitles;
- no unexplained additions;
- no censorship unless project policy requires it.

---

## 14. Structured model output

LLM output must be schema-validated JSON.

Example:

```json
{
  "scene_id": "S034",
  "translations": [
    {
      "cue_ids": [431],
      "meaning": "warning about escalating risk",
      "translation": "...",
      "confidence": 0.97,
      "ambiguity": false,
      "notes": null
    }
  ]
}
```

The application reconstructs subtitle formats.

---

## 15. Sorani normalization

Deterministic normalization stage must handle:
- Arabic `ك` vs Kurdish `ک`;
- Arabic `ي` vs Kurdish `ی`;
- `ە`;
- RTL marks;
- spacing;
- quotation marks;
- punctuation;
- ellipses;
- dashes;
- brackets;
- numerals;
- names.

Normalization is unit-tested.

---

## 16. Subtitle adaptation

Start with original English timing.

For each translated cue compute:
- duration;
- CPS;
- CPL;
- line count;
- min gap;
- line break quality;
- shot alignment.

When a cue fails:
1. rewrite more concisely without losing meaning;
2. improve line break;
3. merge/split semantic units;
4. reallocate timing safely;
5. extend duration if safe;
6. flag for human review.

Never destroy good timing by default.

---

## 17. Quality gate

Three dimensions:

### Semantic
- omission;
- addition;
- negation;
- number errors;
- names;
- tense;
- joke/idiom loss;
- plot leakage.

### Linguistic
- unnatural Sorani;
- grammar;
- mixed Kurmanji;
- script errors;
- terminology inconsistency;
- awkward literal phrasing.

### Technical
- CPS;
- CPL;
- duration;
- overlaps;
- gaps;
- >2 lines;
- malformed tags;
- RTL issues;
- untranslated English.

---

## 18. Second-model verification

Only uncertain lines go to a second model.

Verifier returns:
- agree;
- disagree;
- alternative;
- confidence;
- reason.

It never silently overwrites the primary output.

---

## 19. Human review queue

Human reviewers focus on exceptions.

Show:
- video preview;
- source cue;
- surrounding dialogue;
- intended meaning;
- current translation;
- alternative;
- issue reason;
- technical metrics;
- glossary terms.

Actions:
- accept;
- edit;
- choose alternative;
- rerun;
- add glossary entry;
- mark source wrong;
- mark intentional.

---

## 20. Project modes

### FAST
Existing subtitle → context-aware translation → basic QC.

### PROFESSIONAL
Source validation → context → semantic translation → normalization → full QC → exception verification.

### MASTER
Everything in Professional + stronger source validation + second-model semantic check + mandatory human approval.

Default: **Professional**.

---

## 21. Non-goals for v1

Do not spend v1 resources on:
- custom ASR training;
- multilingual expansion;
- dubbing as primary feature;
- deep cloud collaboration;
- full broadcast delivery stack;
- OOONA clone;
- custom waveform editor.

---

## 22. Definition of #1 quality

Success is not:
- model count;
- speed;
- zero humans;
- flashy UI.

Success is:
- reviewers say the Sorani sounds natural;
- context is preserved;
- semantic errors are rare and surfaced;
- timing is professional;
- repeated names/terms stay consistent;
- human edits concentrate on genuinely difficult lines.

---

## 23. Mandatory benchmark policy

No model, prompt, or pipeline change becomes default unless it beats the current production system on the Hawsub cinematic English → Sorani benchmark.

Do not deploy because a model is newer.
Deploy because it performs better on our actual target material.
