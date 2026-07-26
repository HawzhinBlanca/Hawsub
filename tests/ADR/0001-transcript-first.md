# ADR 0001 — Transcript-first source strategy

## Decision
Prefer existing professional English subtitle/transcript sources before ASR.

## Why
- better timing;
- preserves narrative intent;
- avoids unnecessary transcription errors;
- reduces compute/API cost.

## Consequence
ASR becomes fallback/verifier, not default.
