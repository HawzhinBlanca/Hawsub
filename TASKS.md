# Hawsub Engineering Tasks

## Milestone 0 — Repository and fork hygiene

- [ ] Fork pyVideoTrans
- [ ] Document upstream version/commit
- [ ] Add upstream remote
- [ ] Define merge strategy
- [ ] Add CI
- [ ] Add typed linting/static checks
- [ ] Add unit test runner
- [ ] Add pre-commit hooks
- [ ] Add structured logging
- [ ] Add `.env.example`
- [ ] Add secrets policy
- [ ] Add architecture docs to repo

## Milestone 1 — Sorani target foundation

- [ ] Add `ckb` target language
- [ ] Add explicit Sorani label in UI
- [ ] Ensure UTF-8 end-to-end
- [ ] Implement Kurdish Unicode normalization
- [ ] Implement RTL-safe rendering/export
- [ ] Add Sorani punctuation normalization
- [ ] Add Sorani style guide config
- [ ] Add unit tests for normalization
- [ ] Add sample Sorani SRT fixtures

## Milestone 2 — Transcript-first ingest

- [ ] FFprobe subtitle/audio enumeration
- [ ] Sidecar subtitle scan
- [ ] Track language detection
- [ ] Track type detection: full/forced/SDH
- [ ] Source ranking
- [ ] Source provenance
- [ ] Manual source override
- [ ] Text subtitle extraction
- [ ] Bitmap subtitle detection
- [ ] ASR fallback trigger only when needed

## Milestone 3 — English verification

- [ ] faster-whisper local adapter
- [ ] Segment-level text/audio mismatch scoring
- [ ] Missing-speech detector
- [ ] Suspicious-name detector
- [ ] Foreign-language speech detector
- [ ] Tier-2 anomaly queue
- [ ] Tier-3 multimodal arbitration interface
- [ ] Audio clip extraction/caching

## Milestone 4 — Context engine

- [ ] Movie Bible schema
- [ ] Series Bible schema
- [ ] Season Bible schema
- [ ] Episode Bible schema
- [ ] Character graph
- [ ] Relationship notes
- [ ] Glossary store
- [ ] Plot-state summaries
- [ ] Scene summaries
- [ ] Relevant-context selector
- [ ] Context hashing/versioning

## Milestone 5 — Scene segmentation

- [ ] Detect scene boundaries
- [ ] Group 10–30 cue semantic batches
- [ ] Preserve cue identity across groups
- [ ] Include previous/next summaries
- [ ] Avoid splitting strong dialogue units
- [ ] Add unit/integration tests

## Milestone 6 — Provider abstraction

- [ ] `SemanticModel` interface
- [ ] Gemini provider
- [ ] OpenAI provider
- [ ] Anthropic provider
- [ ] OpenRouter provider
- [ ] Local OpenAI-compatible provider
- [ ] Schema validation
- [ ] Retry/backoff
- [ ] Rate-limit handling
- [ ] Provider health checks
- [ ] Model config UI

## Milestone 7 — Semantic translation

- [ ] Semantic interpretation prompt
- [ ] Meaning-first translation prompt
- [ ] Structured JSON output
- [ ] Translation memory
- [ ] Glossary injection
- [ ] Character voice/context injection
- [ ] Ambiguity flagging
- [ ] No silent fallback to generic NMT
- [ ] Prompt versioning

## Milestone 8 — Foreign dialogue routing

- [ ] Detect foreign-dialogue cues
- [ ] Preserve intentional narrative opacity
- [ ] Route translated foreign speech
- [ ] Flag accidentally missing subtitles
- [ ] Exception transcription path
- [ ] Unit tests for all four cases

## Milestone 9 — Subtitle adaptation

- [ ] CPS calculator
- [ ] CPL calculator
- [ ] line-count validator
- [ ] minimum gap validator
- [ ] duration validator
- [ ] semantic line breaking
- [ ] concise rewrite request path
- [ ] merge/split cues
- [ ] selective retiming
- [ ] configurable QC profiles

## Milestone 10 — QC engine

- [ ] Semantic omission check
- [ ] Semantic addition check
- [ ] Negation check
- [ ] Number/entity consistency
- [ ] Name consistency
- [ ] Terminology consistency
- [ ] Kurmanji contamination heuristics
- [ ] Unicode/RTL checks
- [ ] untranslated-English check
- [ ] malformed-tag check
- [ ] overall confidence score

## Milestone 11 — Second-model verification

- [ ] Verification interface
- [ ] Trigger thresholds
- [ ] Store verifier result
- [ ] Never overwrite silently
- [ ] Alternative translation comparison
- [ ] Human escalation rules

## Milestone 12 — Review queue

- [ ] Severity-based filters
- [ ] Scene filters
- [ ] Character filters
- [ ] Issue filters
- [ ] Show surrounding context
- [ ] Show semantic meaning
- [ ] Show alternatives
- [ ] Accept/edit/rerun
- [ ] Add-to-glossary action
- [ ] Mark intentional/source-wrong actions

## Milestone 13 — Export

- [ ] SRT
- [ ] ASS
- [ ] VTT
- [ ] bilingual debug export
- [ ] QC report
- [ ] project archive
- [ ] Subtitle Edit handoff

## Milestone 14 — Benchmark suite

- [ ] 500–1,000 expert-reviewed examples
- [ ] multiple genres
- [ ] idioms
- [ ] sarcasm
- [ ] slang
- [ ] profanity
- [ ] threats
- [ ] emotional dialogue
- [ ] legal/medical terminology
- [ ] names
- [ ] wordplay
- [ ] foreign-language inserts
- [ ] acceptable alternatives
- [ ] unacceptable literal translations

## Milestone 15 — Production hardening

- [ ] crash recovery
- [ ] resumable jobs
- [ ] scene-level checkpoints
- [ ] request caching
- [ ] API outage handling
- [ ] malformed JSON recovery
- [ ] quota exhaustion handling
- [ ] large-project stress tests
- [ ] security review
- [ ] privacy mode
- [ ] audit logs

## Milestone 16 — Acceptance testing

- [ ] 3 complete movies
- [ ] 3 TV episodes
- [ ] full professional review
- [ ] zero broken exports
- [ ] zero lost cues
- [ ] zero systematic RTL corruption
- [ ] zero systematic Kurmanji contamination
- [ ] no timestamp corruption
- [ ] critical semantic error threshold met
- [ ] reviewer edit-rate measured
