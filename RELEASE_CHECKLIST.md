# Hawsub Release Checklist

## Build
- [ ] Reproducible build
- [ ] Version tagged
- [ ] Upstream commit documented
- [ ] Dependency lock updated
- [ ] License notices updated

## Tests
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Regression tests pass
- [ ] Gold benchmark passes
- [ ] Full-project smoke test passes

## Subtitle integrity
- [ ] No cue loss
- [ ] No cue reordering
- [ ] No timestamp corruption
- [ ] No invalid SRT/ASS/VTT
- [ ] RTL rendering checked

## Sorani quality
- [ ] Unicode normalization passes
- [ ] No systematic Kurmanji contamination
- [ ] Terminology consistency passes
- [ ] Names consistent
- [ ] Untranslated-English detector passes

## Reliability
- [ ] Resume after crash tested
- [ ] Provider timeout tested
- [ ] Malformed JSON tested
- [ ] Quota exhaustion tested
- [ ] Retry policy tested

## Privacy/security
- [ ] API keys not logged
- [ ] no entire-media upload by default
- [ ] logs redacted
- [ ] dependency scan completed

## Human validation
- [ ] Professional reviewer signoff
- [ ] Critical semantic error rate acceptable
- [ ] Reviewer edit-rate within target
- [ ] No blocker issues
