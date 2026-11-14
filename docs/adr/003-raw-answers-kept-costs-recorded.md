# ADR-003: Every paid answer is kept; every cost is recorded

*Status: accepted · 2026-11-14 · Martin*

## Context

Evaluating engines means re-scoring the same answers many times as references, metrics and normalisation change.
Paying again for the same audio is waste. A result nobody can reproduce is not a result.

## Decision

- Every answer from a paid API is saved verbatim under `data/events/<event>/raw/<engine>/<piece>.json` before it
  is parsed.
- Every call records engine, model, parameters, price at run time, cost, and wall time.
- Evaluation and reports read the saved answers; they never call an API.
- A rerun of an engine on a piece that already has an answer is skipped unless `--force` is given.

## Consequences

`data/` grows; it is local and git-ignored (ADR-005). Contract tests use saved answers as fixtures. These are
license-clean fixtures, never TA3 audio.

## Enforced by

The `stt-engine` skill (the adapter checklist); contract tests; review.
