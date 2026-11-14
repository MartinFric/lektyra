# ADR-001: Python 3.12, uv, mypy strict, data parsed at the boundary

*Status: accepted · 2026-11-14 · Martin*

## Context

Diarization (pyannote), voice embeddings (SpeechBrain, WeSpeaker), speech detection (Silero VAD) and the metrics
(jiwer, pyannote.metrics) exist natively only in Python. Speech-to-text is HTTP and could be any language. Martin's
other projects are typed strictly (TypeScript without casts, Rust); Python must not be the weak spot.

## Decision

- Python 3.12, managed by **uv** (`pyproject.toml` + `uv.lock`).
- **mypy `--strict`** over `src/` and `tests/`; **ruff** for lint and format.
- **No `cast()`, no `# type: ignore`, no `Any`** outside `src/lektyra/adapters/`. The untyped ML libraries are
  touched only inside adapters, which return typed domain objects.
- Data is **parsed where it enters**: pydantic models for API answers, settings, CLI input and stored JSON. A
  mismatch fails loudly at the boundary.
- Domain types are frozen dataclasses. States are `Literal` unions, matched exhaustively.

## Consequences

Adapters carry the typing debt of the libraries they wrap and nothing else does. A new library needs an adapter,
not a scattering of ignores.

## Enforced by

pre-commit L3 (`cast(`, `type: ignore`, `Any` outside adapters) and L6 (`ruff`, `ruff format`, `mypy --strict`, fast tests); the post-edit guard; `hook-tests.sh`.
