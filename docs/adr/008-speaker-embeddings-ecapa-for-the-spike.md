# ADR-008: Speaker embeddings for the spike: SpeechBrain ECAPA, our own clustering

*Status: accepted · 2026-11-14 · Martin ("keep soniox and hf for later"; "continue with all you can")*

## Context

The plan named pyannote `speaker-diarization-community-1` for diarization. It is gated on Hugging Face: it needs a
token and accepting its conditions, which Martin deferred. Speaker separation and voice profiles (ADR-004) need
voice embeddings now.

## Decision

- Embeddings come from **SpeechBrain ECAPA-TDNN** (`speechbrain/spkrec-ecapa-voxceleb`, 192 numbers per clip). It is
  public, needs no token, and runs on the CPU (`adapters/embed/speechbrain_ecapa.py`). Torch and SpeechBrain are
  the `voice` dependency group, a default group for the spike.
- Diarization is **our own, pure and tested** (`domain/diarization.py`):
  1. speech regions from Silero;
  2. 2 s windows every 1 s;
  3. groups of 3 windows;
  4. average-linkage clustering on cosine distance (threshold 0.55);
  5. each window reassigned to its nearest centroid;
  6. short runs absorbed into turns.
- The model and the Hugging Face cache live under `data/models/` (ADR-005).
- pyannote stays the comparison point: once the token exists, its diarization is a second `Diarizer` adapter and
  DER decides between them (eval skill).

## Consequences

Diarization works now, on every machine, without an account. Overlapping speech is not modelled (a window gets one
speaker). pyannote handles overlap better, which the comparison will show on video A. Embedding quality also bounds
the voice profiles. A second embedder (WeSpeaker, via pyannote) is compared there too.

## Enforced by

Unit tests of `domain/diarization.py` on synthetic embeddings; the diarization numbers in `docs/eval/`.
