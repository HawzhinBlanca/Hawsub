# ADR 0004 — Structured LLM output

## Decision
LLMs return schema-validated JSON, never final SRT/ASS files.

## Why
Deterministic application code should own subtitle structure.

## Consequence
Malformed outputs can be retried without corrupting project files.
