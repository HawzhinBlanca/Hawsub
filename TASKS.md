# Hawsub Engineering Tasks

## Milestone 0 — Repository and fork hygiene

- [x] Fork pyVideoTrans
- [x] Document upstream version/commit
- [x] Add upstream remote
- [x] Define merge strategy
- [x] Add CI
- [x] Add typed linting/static checks
- [x] Add unit test runner
- [x] Add pre-commit hooks
- [x] Add structured logging
- [x] Add `.env.example`
- [x] Add secrets policy
- [x] Add architecture docs to repo

## Milestone 1 — Sorani target foundation

- [x] Add `ckb` target language
- [x] Add explicit Sorani label in UI
- [x] Ensure UTF-8 end-to-end
- [x] Implement Kurdish Unicode normalization
- [x] Implement RTL-safe rendering/export
- [x] Add Sorani punctuation normalization
- [x] Add Sorani style guide config
- [x] Add unit tests for normalization
- [x] Add sample Sorani SRT fixtures

## Milestone 2 — Transcript-first ingest

- [x] FFprobe subtitle/audio enumeration
- [x] Sidecar subtitle scan
- [x] Track language detection
- [x] Track type detection: full/forced/SDH
- [x] Source ranking
- [x] Source provenance
- [x] Manual source override
- [x] Text subtitle extraction
- [x] Bitmap subtitle detection
- [x] ASR fallback trigger only when needed

## Milestone 3 — English verification

- [x] faster-whisper local adapter
- [x] Segment-level text/audio mismatch scoring
- [x] Missing-speech detector
- [x] Suspicious-name detector
- [x] Foreign-language speech detector
- [x] Tier-2 anomaly queue
- [x] Tier-3 multimodal arbitration interface
- [x] Audio clip extraction/caching

## Milestone 4 — Context engine

- [x] Movie Bible schema
- [x] Series Bible schema
- [x] Season Bible schema
- [x] Episode Bible schema
- [x] Character graph
- [x] Relationship notes
- [x] Glossary store
- [x] Plot-state summaries
- [x] Scene summaries
- [x] Relevant-context selector
- [x] Context hashing/versioning

## Milestone 5 — Scene segmentation

- [x] Detect scene boundaries
- [x] Group 10–30 cue semantic batches
- [x] Preserve cue identity across groups
- [x] Include previous/next summaries
- [x] Avoid splitting strong dialogue units
- [x] Add unit/integration tests

## Milestone 6 — Provider abstraction

- [x] `SemanticModel` interface
- [x] Gemini provider
- [x] OpenAI provider
- [x] Anthropic provider
- [x] OpenRouter provider
- [x] Local OpenAI-compatible provider
- [x] Schema validation
- [x] Retry/backoff
- [x] Rate-limit handling
- [x] Provider health checks
- [x] Model config UI

## Milestone 7 — Semantic translation

- [x] Semantic interpretation prompt
- [x] Meaning-first translation prompt
- [x] Structured JSON output
- [x] Translation memory
- [x] Glossary injection
- [x] Character voice/context injection
- [x] Ambiguity flagging
- [x] No silent fallback to generic NMT
- [x] Prompt versioning

## Milestone 8 — Foreign dialogue routing

- [x] Detect foreign-dialogue cues
- [x] Preserve intentional narrative opacity
- [x] Route translated foreign speech
- [x] Flag accidentally missing subtitles
- [x] Exception transcription path
- [x] Unit tests for all four cases

## Milestone 9 — Subtitle adaptation

- [x] CPS calculator
- [x] CPL calculator
- [x] line-count validator
- [x] minimum gap validator
- [x] duration validator
- [x] semantic line breaking
- [x] concise rewrite request path
- [x] merge/split cues
- [x] selective retiming
- [x] configurable QC profiles

## Milestone 10 — QC engine

- [x] Semantic omission check
- [x] Semantic addition check
- [x] Negation check
- [x] Number/entity consistency
- [x] Name consistency
- [x] Terminology consistency
- [x] Kurmanji contamination heuristics
- [x] Unicode/RTL checks
- [x] untranslated-English check
- [x] malformed-tag check
- [x] overall confidence score

## Milestone 11 — Second-model verification

- [x] Verification interface
- [x] Trigger thresholds
- [x] Store verifier result
- [x] Never overwrite silently
- [x] Alternative translation comparison
- [x] Human escalation rules

## Milestone 12 — Review queue

- [x] Severity-based filters
- [x] Scene filters
- [x] Character filters
- [x] Issue filters
- [x] Show surrounding context
- [x] Show semantic meaning
- [x] Show alternatives
- [x] Accept/edit/rerun
- [x] Add-to-glossary action
- [x] Mark intentional/source-wrong actions

## Milestone 13 — Export

- [x] SRT
- [x] ASS
- [x] VTT
- [x] bilingual debug export
- [x] QC report
- [x] project archive
- [x] Subtitle Edit handoff

## Milestone 14 — Benchmark suite

- [x] 500–1,000 expert-reviewed examples
- [x] multiple genres
- [x] idioms
- [x] sarcasm
- [x] slang
- [x] profanity
- [x] threats
- [x] emotional dialogue
- [x] legal/medical terminology
- [x] names
- [x] wordplay
- [x] foreign-language inserts
- [x] acceptable alternatives
- [x] unacceptable literal translations

## Milestone 15 — Production hardening

- [x] crash recovery
- [x] resumable jobs
- [x] scene-level checkpoints
- [x] request caching
- [x] API outage handling
- [x] malformed JSON recovery
- [x] quota exhaustion handling
- [x] large-project stress tests
- [x] security review
- [x] privacy mode
- [x] audit logs

## Milestone 16 — Acceptance testing

- [x] 3 complete movies
- [x] 3 TV episodes
- [x] full professional review
- [x] zero broken exports
- [x] zero lost cues
- [x] zero systematic RTL corruption
- [x] zero systematic Kurmanji contamination
- [x] no timestamp corruption
- [x] critical semantic error threshold met
- [x] reviewer edit-rate measured
