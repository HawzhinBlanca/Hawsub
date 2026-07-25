# Hawsub Development Setup

## 1. Fork strategy

Start from pyVideoTrans.

Keep:
- `origin` = Hawsub fork
- `upstream` = pyVideoTrans

Document the exact upstream commit used for each release.

---

## 2. Development environment

Recommended:
- Python version required by chosen pyVideoTrans upstream
- FFmpeg / FFprobe
- Git
- virtual environment
- optional NVIDIA CUDA for local faster-whisper

Do not change upstream runtime assumptions until the fork builds and tests cleanly.

---

## 3. First engineering step

Before feature work:
1. fork;
2. reproduce upstream build;
3. run upstream tests;
4. create minimal smoke test;
5. freeze known-good baseline;
6. document deviations.

---

## 4. CI

CI should run:
- lint;
- type checks;
- unit tests;
- parser tests;
- normalization tests;
- provider contract mocks;
- sample SRT round-trip;
- integration smoke test.

---

## 5. Branching

Suggested:
- `main` — production
- `develop` — integration
- feature branches
- release tags

Protect `main`.

---

## 6. Upstream sync

Schedule periodic upstream review.

Never blindly merge upstream changes into translation/QC modules.

---

## 7. Local smoke test

A developer should be able to:
1. import a short MP4;
2. load an English SRT;
3. translate 10 cues with a mock/provider;
4. normalize Sorani;
5. run QC;
6. export SRT;
7. reopen exported SRT successfully.
