# ADR-004: A voice profile is derived from its samples; a wrong name is worse than unknown

*Status: accepted · 2026-11-14 · Martin*

## Context

Known people should be named automatically, and a human correction of "Person X" should make the next match
succeed. The same person sounds different in a studio, in the parliament hall and on a phone line. Labelled
profiles per quality would need a label nobody can give reliably.

## Decision

- A profile is a **function of its samples**. It is rebuilt, never patched. Deleting samples undoes a wrong
  confirmation. A new embedding model means re-embedding and rebuilding.
- Matching is **k nearest confirmed samples** (pgvector) after **score normalisation** (adaptive s-norm against a
  cohort). Centroids are only a cache.
- Quality (overlap, length, noise) is a gate and a weight, not a key. The channel is stored as metadata.
- Provenance on every sample: `auto` / `human_confirmed` / `human_corrected`. Automatic matches feed the profile
  only above a high score, with a low weight.
- A human correction of a wrong match writes a **rejection** (a hard negative).
- **Thresholds are set for zero false names first, then for hits.** "Unknown" is an acceptable answer; a wrong name
  is not.

## Consequences

Samples have to be stored (embeddings always; short audio clips or event references to re-embed later, local only
per ADR-005). The profile database is biometric data: see ADR-005.

## Enforced by

The `voice-profiles` skill; unit tests of `domain/profiles.py` and `domain/matching.py` (rebuild is deterministic,
a rejection is never matched again); the profiles report.
