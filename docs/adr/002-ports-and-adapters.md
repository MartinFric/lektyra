# ADR-002: Ports and adapters; the domain is pure; OpenRouter is the speech-to-text gateway

*Status: accepted · 2026-11-14 · Martin*

## Context

The spike compares about ten speech-to-text engines, two embedding models and more than one diarizer, and has to
run the same logic on a live stream and on a recorded video. Engines change prices, names and retire (HTN
ADR-068). OpenRouter exposes ~30 transcription models behind one API.

## Decision

- `src/lektyra/domain/`: **pure**. No I/O, no clock, no network, no imports from `adapters/` or `app/`. It covers
  cutting, stitching, alignment, matching, profiles, claims and metrics, and is fully unit-tested.
- `src/lektyra/ports.py`: `Protocol`s: `MediaSource`, `SpeechDetector`, `Transcriber`, `Diarizer`, `Embedder`,
  `Repository`.
- `src/lektyra/adapters/`: one module per outside thing; adapters only translate.
- `src/lektyra/app/`: one use case per module, wiring ports together. `cli.py` only parses arguments and calls
  `app`.
- **Speech-to-text goes through OpenRouter.** One adapter serves every OpenRouter model, where a model is a name.
  A provider OpenRouter lacks (Soniox) gets its own adapter behind the same `Transcriber` port.

## Consequences

A new OpenRouter model is a line, not code. A new provider is one module plus one contract test. Domain logic can
be tested with synthetic data in milliseconds.

## Enforced by

pre-commit L4 (`domain/` imports nothing from `adapters`/`app`/`cli`/`settings`; no I/O modules, `open(`, file reads
or the clock there); the `architect` skill; review.
