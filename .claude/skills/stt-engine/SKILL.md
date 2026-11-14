---
name: stt-engine
description: Adding or changing a speech-to-text engine in lektyra (OpenRouter models, Soniox, others): the Transcriber port, saving raw answers, recording cost, hallucination filtering, contract tests. Use before touching src/lektyra/adapters/stt/.
---

# Speech-to-text engines

## The rule (ADR-002, ADR-003)

- **OpenRouter is the gateway.** One adapter (`adapters/stt/openrouter.py`) serves every OpenRouter transcription
  model; an engine there is a model id in the engine list (`lektyra catalog` lists them with today's price:
  `/api/v1/models?output_modalities=transcription`, price is per second of audio).
- A provider OpenRouter lacks (Soniox) gets its own adapter behind the same `Transcriber` port.

## Checklist for an adapter call

1. **Before calling**: if `data/events/<event>/raw/<engine>/<piece>.json` exists, read it and do not call
   (`--force` to re-run).
2. **Send** the piece (FLAC 16 kHz mono, or what the engine requires, converted by ffmpeg). Ask for word timestamps
   and `verbose_json` where offered; `temperature: 0`. Zero data retention on where the provider offers it
   (`provider.zdr`); record whether it was.
3. **Save the raw answer verbatim** before parsing (ADR-003).
4. **Record**: engine, model, parameters, list price at run time, cost (from the answer's usage when given, else
   seconds × price), wall time.
5. **Parse** with a pydantic model of that engine's answer into domain `TimedWord`s and segments. Times are relative
   to the piece: add `piece.start_ms` (which includes the overlap) to get stream time; `stitch` joins pieces.
6. **Hallucination filter** (from HTN's recorder): drop segments with `no_speech_prob > 0.6 and avg_logprob < -1.0`,
   and known invented phrases (subtitle credits, "Ďakujem za pozornosť" on silence). The filter is domain code.
7. Language: unset by default (auto); `--language sk` pins Slovak. Record which.

## Tests

A contract test per adapter with a saved answer fixture: a license-clean recording (LibriSpeech CC BY or generated
speech), **never TA3 audio or its transcript**. It asserts parsing, timing offsets and the filter. No network in
tests.
