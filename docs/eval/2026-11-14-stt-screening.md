# Speech-to-text screening round, 2026-11-14

**Question:** which OpenRouter speech-to-text engines are worth a full run on Slovak TV, and with what settings?

**Data:**
- the five spike videos (spike-plan §2), one window each:
  - A, *V politike* 24.9.2023, Fico + Kollár + moderator: 20:00–30:00, with cross-talk;
  - B, *V politike* 15.5.2022, Fico + Kollár: 15:00–20:00;
  - C, TA3 interview with Fico 12.1.2025: 20:00–25:00;
  - D1, NR SR question time with Fico (JOJ 24, YouTube): 05:00–10:00;
  - D2, government press conference Fico + Takáč (Úrad vlády, YouTube): 10:00–15:00;
- pieces cut by ADR-006 (45–75 s);
- `language=sk` pinned;
- every answer saved under `data/` (ADR-003). No audio or transcript is in this report (ADR-005).

**Status:** provisional. Without references, "agreement" is a consensus proxy: engines can agree on the same wrong
name. Martin's references (K7) turn this into WER, names and numbers accuracy.

## Agreement with the other engines

Mean share of an engine's words that the others also heard nearby (`domain/compare.covered`, 10 s rows, ±1 row).

| engine (`@sk`) | A (cross-talk) | B | C | D1 (hall) | D2 (press room) |
|---|---|---|---|---|---|
| elevenlabs/scribe-v2 | **0.74** | **0.71** | **0.81** | **0.83** | **0.81** |
| google/gemini-3.5-transcribe | 0.73 | 0.69 | 0.80 | **0.83** | **0.81** |
| x-ai/grok-stt-2.0 | 0.71 | 0.70 | 0.79 | **0.83** | 0.79 |
| mistralai/voxtral-small-transcribe-3-0 | 0.72 | 0.68 | **0.81** | 0.80 | 0.79 |
| deepgram/nova-3 | 0.70 | 0.67 | 0.79 | 0.81 | 0.62 |
| openai/whisper-large-v3 | 0.67 | 0.60 | 0.73 | 0.74 | 0.74 |
| openai/gpt-transcribe | 0.64 | 0.64 | 0.71 | 0.73 | 0.70 |
| openai/gpt-4o-transcribe | 0.60 | 0.60 | 0.66 | 0.68 | 0.68 |
| nvidia/parakeet-tdt-0.6b-v3 | 0.58 | 0.53 | 0.66 | 0.70 | 0.69 |

Chirp 3 is not in the table: it answered only half the pieces (see below). The top four engines stay together in
every window. A (heated cross-talk) is the hardest window for all of them.

## Practical numbers (the 36 screening pieces per engine)

| engine | answered | $ per audio hour | s per ~60 s piece | zero data retention | word times |
|---|---|---|---|---|---|
| elevenlabs/scribe-v2 | 36/36 | 0.220 | 6.8 | **yes** | yes |
| google/gemini-3.5-transcribe | 36/36 | 0.416 | 6.2 | no | yes |
| x-ai/grok-stt-2.0 | 36/36 | **0.100** | 3.6 | no | yes |
| mistralai/voxtral-small-transcribe-3-0 | 36/36 | 0.238 | 4.9 | **yes** | no (segments only) |
| deepgram/nova-3 | 34/36 | 0.258 | 1.8 | **yes** | yes |
| openai/whisper-large-v3 | 36/36 | **0.034** | 3.9 | **yes** | yes |
| openai/gpt-transcribe | 36/36 | 0.272 | 3.6 | no | no (plain json) |
| openai/gpt-4o-transcribe | 36/36 | 0.274 | 5.4 | no | no (plain json) |
| nvidia/parakeet-tdt-0.6b-v3 | 36/36 | 0.068 | 1.8 | **yes** | yes |
| google/chirp-3 | 18/36 | 0.968 | 9.0 | **yes** | no (plain json) |
| assemblyai/universal-3-6-pro | 0/36 with `sk`; auto only | 0.300 | 3.2 | yes | yes |

The whole screening round, smoke test included, cost about **$1.45** on Martin's OpenRouter key.

## Findings

1. **Pin the language.** On auto-detect, AssemblyAI heard Slovak as Polish-like gibberish and Deepgram returned
   nothing. With `language=sk`, Deepgram works. The other engines are fine either way.
2. **AssemblyAI cannot be told the language through OpenRouter.** `sk`, `slk`, `sk-SK` and `Slovak` all give
   "Provider returned 400". On auto-detect it mishears Slovak. It is out unless used directly.
3. **Chirp 3 fails on pieces longer than about 60 s.** That is Google's synchronous limit, and lektyra's pieces run
   up to 75 s. It is also the most expensive engine. It is out unless pieces are capped at 60 s for it.
4. **OpenAI's GPT transcribers and Chirp answer plain `json` only**: text, no times. The adapter falls back to it
   automatically. Their text is placed in rows by spreading it evenly over the piece, which also lowers their
   agreement a little.
5. **Grok reports its language as "en"** but transcribes Slovak correctly. The language field is not to be trusted.
6. **Zero data retention**, as OpenRouter offers it today:
   - available: ElevenLabs, Voxtral, Deepgram, Whisper, Parakeet, Chirp;
   - not available: Gemini, Grok, the OpenAI GPT models.
   A public broadcast is fine either way. Anything private later should use a zero-retention engine.
7. **Voxtral catches cross-talk others drop** (seen in A). It gives no word times through OpenRouter, so it cannot
   place words on speakers precisely.

## Decision (provisional, until the references)

- **Final round** on all five full videos: **ElevenLabs Scribe v2, Grok STT 2.0, Gemini 3.5 Transcribe**. These are
  the top agreement group with word times, which speaker alignment needs. About 4 h of audio, about $3.
- Keep Voxtral as the cross-talk second opinion for the claim quote check (spike-plan §8).
- If the references confirm the order, the default engine is **ElevenLabs** (zero-retention, word times, top in
  every window) with **Grok** as the cheap second opinion. ADR-009 records the choice then.
