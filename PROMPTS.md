# Hawsub Prompt Contracts

Prompts are versioned production assets. Keep them in separate files in implementation.

---

## 1. Semantic interpretation prompt

### Purpose
Determine what dialogue actually means in context before translating.

### Required instructions

- Analyze intended meaning, not just literal wording.
- Use scene context, speaker relationship, plot state, and surrounding dialogue.
- Identify idioms, sarcasm, threats, jokes, implied meaning, and ambiguity.
- Do not translate yet.
- Do not invent information.
- Preserve deliberate ambiguity.
- Return structured JSON.

### Output shape

```json
{
  "scene_id": "...",
  "items": [
    {
      "cue_ids": [1],
      "meaning": "...",
      "tone": "...",
      "register": "...",
      "subtext": "...",
      "ambiguity": 0.0,
      "notes": null
    }
  ]
}
```

---

## 2. Sorani translation prompt

### Target definition

Translate into:
- Central Kurdish / Sorani (`ckb`);
- Arabic-based Central Kurdish script;
- natural usage appropriate to the Kurdistan Region of Iraq;
- do not output Kurmanji.

### Translation rules

- Translate intended meaning, not individual words.
- Preserve tone, intent, humor, sarcasm, threat level, politeness, and character voice.
- Localize idioms naturally.
- Keep wording concise enough for subtitles.
- Do not explain jokes.
- Do not add plot information.
- Do not remove ambiguity that exists in the source.
- Use glossary terms exactly when marked mandatory.
- Respect names and terminology.
- Return JSON only.

---

## 3. Translation verifier prompt

### Purpose
Judge an existing Sorani translation.

Check:
- semantic fidelity;
- omissions/additions;
- negation;
- names/numbers;
- idiomatic naturalness;
- accidental Kurmanji;
- awkward literal phrasing;
- terminology consistency.

Return:
```json
{
  "decision": "agree|disagree|uncertain",
  "severity": "none|minor|major|critical",
  "reason": "...",
  "alternative": null,
  "confidence": 0.0
}
```

---

## 4. Audio arbitration prompt

Input:
- source subtitle;
- short English audio clip;
- nearby cues;
- scene context.

Determine:
- whether source text matches spoken dialogue;
- whether a mismatch is intentional paraphrase;
- names/terms;
- ambiguity;
- foreign-language speech.

Do not alter timing.

---

## 5. Movie Bible prompt

Extract:
- synopsis;
- setting;
- period;
- major characters;
- relationships;
- recurring terminology;
- organizations;
- places;
- recurring expressions;
- translation-sensitive concepts.

Avoid spoilers beyond the project's currently available context when used episodically.

---

## 6. Prompt versioning

Every provider run stores:
- prompt name;
- prompt version;
- model;
- provider;
- config hash.

No prompt edits directly in application code.
