# Hawsub Benchmark Specification

## Goal

Measure real cinematic English → Sorani subtitle quality.

Do not rely on generic multilingual leaderboards.

---

## Dataset

Initial target:
- 500–1,000 hand-curated examples.

Later:
- 5,000+ examples across projects.

Include:
- ordinary dialogue;
- idioms;
- sarcasm;
- humor;
- slang;
- profanity;
- threats;
- romance;
- family dialogue;
- crime;
- legal language;
- medical language;
- politics;
- historical language;
- technical jargon;
- accents;
- invented terminology;
- names;
- wordplay;
- foreign-language inserts;
- ambiguity;
- short subtitle constraints.

---

## Gold annotation

Each item should contain:

```json
{
  "source": "...",
  "context": "...",
  "intended_meaning": "...",
  "gold_sorani": "...",
  "acceptable_alternatives": ["..."],
  "unacceptable_literal_examples": ["..."],
  "notes": "..."
}
```

---

## Human rating dimensions

Score 1–5:
- meaning preservation;
- natural Sorani;
- idiomaticity;
- character voice;
- cultural appropriateness;
- grammar;
- terminology;
- concision;
- subtitle readability;
- timing fitness.

Track separately:
- hallucination;
- omission;
- critical semantic error.

---

## Model comparison

Benchmark:
- current production Gemini configuration;
- newer Gemini generations;
- current Claude;
- current OpenAI model;
- DeepL where appropriate;
- any new serious candidate.

No model becomes default because it is newer.

---

## Release rule

A new model/prompt must:
- improve weighted human score;
- not increase critical errors;
- not materially increase reviewer edit rate;
- pass full-project regression tests.
