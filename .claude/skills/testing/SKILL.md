---
name: testing
description: How lektyra is tested: unit tests of the pure domain on synthetic data, contract tests of adapters on license-clean fixtures, slow integration tests, replay=live tests, and "a fix starts with a failing test". Use before writing or changing tests or fixing a bug.
---

# Testing

| kind | where | what | runs in |
|---|---|---|---|
| unit | `tests/unit/` | domain logic on synthetic curves, words, embeddings | pre-commit (fast) |
| contract | `tests/contract/` | an adapter's parsing on saved, license-clean fixtures or synthetic snippets | pre-commit (fast) |
| integration | `tests/integration/`, `@pytest.mark.slow` | ffmpeg, Postgres (compose), real files | pre-push |

## Rules

- **A fix starts with a failing test** that reproduces the bug (the tripwire). Then fix, and watch it pass.
- **Replay = live** is tested: feeding a stream in one batch and frame by frame gives identical results
  (`test_replay_equals_live_…`). Every new streaming component gets the same test.
- **No real voices, no broadcast audio, no TA3 transcripts** in fixtures (ADR-005). Use synthetic signals,
  LibriSpeech (CC BY 4.0), or generated speech.
- **No network** in tests. No wall clock: time is passed in.
- **No sleeping.** No test depends on timing.
- Test names say the behaviour: `test_a_cut_never_lands_inside_a_word`, not `test_cut_2`.
- A rule that guards something (a hook, a filter, a threshold) gets a test that shows it **can fire**, not just
  that it passes on good input.
