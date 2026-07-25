# Hawsub Reliability & Security

## Reliability

### Required
- resumable jobs;
- scene-level checkpoints;
- idempotent stages;
- exponential backoff;
- request timeout;
- max retries;
- provider rate-limit handling;
- malformed JSON recovery;
- API outage handling;
- quota exhaustion handling;
- local cache;
- crash-safe project state.

### Rule
A two-hour movie must never restart from zero because one scene failed.

---

## Secrets

Store API keys in:
- environment variables;
- OS keychain;
- encrypted secret store.

Never:
- hardcode keys;
- commit keys;
- log keys.

---

## Privacy

Default behavior:
- do not upload entire movie;
- only upload text/context required for translation;
- only upload short audio clips for flagged ambiguous segments;
- expose provider/privacy status clearly in UI.

---

## Logs

Structured logs should include:
- project ID;
- stage;
- scene;
- provider;
- model;
- latency;
- retry count;
- status.

Do not log:
- API secrets;
- unnecessary media content.

---

## Auditability

Record:
- source provenance;
- model version;
- prompt version;
- config version;
- translation changes;
- reviewer decisions.

---

## Supply-chain security

- pin critical dependencies;
- run vulnerability scanning;
- review licenses;
- verify downloaded binaries/checksums where practical.
