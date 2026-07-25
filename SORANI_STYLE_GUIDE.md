# Hawsub Sorani Style Guide

## Scope

This guide defines the default Hawsub style for Central Kurdish / Sorani (`ckb`) cinematic subtitles.

Project-specific overrides are allowed.

---

## 1. Script

Use Arabic-based Central Kurdish script.

Avoid accidental:
- Latin Kurmanji;
- Arabic-character substitutions where Kurdish code points are preferred.

Normalize common code-point inconsistencies.

Examples:
- Arabic `ك` → Kurdish `ک` where appropriate
- Arabic `ي` → Kurdish `ی` where appropriate

Treat `ە` consistently.

---

## 2. Naturalness

Subtitles should sound like natural Sorani dialogue, not translated English syntax.

Prefer:
- idiomatic phrasing;
- conversational rhythm;
- culturally normal sentence order.

Avoid:
- literal English constructions;
- unnecessary pronouns;
- over-explanation;
- stiff dictionary phrasing.

---

## 3. Meaning priority

Priority:
1. intended meaning
2. character voice
3. natural Sorani
4. subtitle concision
5. literal wording

Never preserve literal wording at the cost of meaning.

---

## 4. Character consistency

Maintain:
- names;
- titles;
- honorifics;
- nicknames;
- recurring phrases;
- formality level.

Series projects must persist these decisions across episodes.

---

## 5. Profanity

Do not sanitize automatically.

Follow project policy:
- preserve force;
- preserve tone;
- avoid stronger wording than source unless natural equivalence requires it.

---

## 6. Foreign dialogue

If the source English subtitle intentionally hides meaning, Hawsub must not reveal it.

Example:
`[Speaking Spanish]`
→ translate the indicator, not the hidden dialogue.

---

## 7. Punctuation and RTL

Use RTL-safe punctuation handling.

Normalize:
- quotation marks;
- ellipses;
- dashes;
- brackets;
- spacing around punctuation.

Test rendering in:
- SRT;
- ASS;
- Subtitle Edit;
- at least one common video player.

---

## 8. Numbers

Use the project-configured numeral policy consistently.

Do not silently change:
- dates;
- money;
- measurements;
- addresses;
- codes.

---

## 9. Line breaking

Prefer semantic breaks:
- clause boundaries;
- phrase boundaries;
- punctuation boundaries.

Avoid splitting:
- names;
- fixed expressions;
- noun + modifier units;
- tightly bound grammatical structures.

---

## 10. Translation memory

Approved human corrections become preferred references, but context can override prior phrasing.
