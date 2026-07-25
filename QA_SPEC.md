# Hawsub QA Specification

## 1. Quality dimensions

Every cue is evaluated across:

1. Source confidence
2. Semantic fidelity
3. Sorani naturalness
4. Terminology consistency
5. Technical subtitle compliance
6. Overall confidence

---

## 2. Semantic QA

Critical failures:
- meaning reversed;
- negation lost/added;
- subject/object swapped;
- number/date changed;
- name/entity changed;
- plot information added;
- key meaning omitted.

Major failures:
- idiom translated literally;
- sarcasm flattened;
- register wrong;
- relationship/politeness wrong;
- tense/aspect materially changed.

Minor failures:
- slightly awkward wording;
- non-critical stylistic inconsistency.

---

## 3. Linguistic QA

Check:
- Central Kurdish/Sorani script;
- no accidental Kurmanji output;
- natural Iraqi-Kurdistan Sorani;
- punctuation;
- spacing;
- names;
- recurring terminology;
- grammar;
- fluency;
- concise subtitle phrasing.

---

## 4. Technical QA

Configurable by profile.

Check:
- max lines;
- preferred/hard CPS;
- preferred/hard CPL;
- minimum duration;
- maximum duration;
- minimum gap;
- overlap;
- shot-change rules;
- malformed tags;
- invalid encoding;
- duplicate cues;
- untranslated source text;
- RTL rendering safety.

---

## 5. Example default house profile

```yaml
max_lines: 2
preferred_cps: 17
hard_max_cps: 20
preferred_cpl: 40
hard_max_cpl: 42
min_duration_ms: 800
min_gap_ms: 80
```

These are defaults, not universal rules.

---

## 6. Confidence policy

Suggested:
- `>= 0.94`: auto-pass if no hard-rule violation
- `0.85–0.939`: review if semantic/linguistic risk exists
- `< 0.85`: mandatory review
- any critical semantic flag: mandatory review regardless of score

Confidence must not be generated only by the same model that produced the translation.

Combine:
- source reliability;
- model self-assessment;
- deterministic checks;
- second-model disagreement;
- heuristic signals.

---

## 7. Regression gates

A release fails if it causes:
- increased critical semantic errors;
- increased untranslated-English rate;
- worse RTL/Unicode failures;
- worse terminology consistency;
- significant increase in reviewer edit rate;
- benchmark score regression beyond allowed tolerance.

---

## 8. Full-project acceptance

Before v1 production:

Test at least:
- 3 movies
- 3 TV episodes
- multiple genres

Required:
- zero corrupted subtitle files;
- zero lost cues;
- zero timestamp reordering;
- zero systemic script errors;
- no systemic Kurmanji contamination;
- no unresolved critical semantic errors;
- professional reviewer signoff.
