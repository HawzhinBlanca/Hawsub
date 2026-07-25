# ADR 0002 — Model independence

## Decision
All semantic/translation models must be accessed through provider adapters.

## Why
Model quality and availability change quickly.

## Consequence
No hardcoded Gemini/OpenAI/Claude assumptions in domain logic.
