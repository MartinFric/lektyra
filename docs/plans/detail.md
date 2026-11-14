# lektyra board detail

## K10

*doing, 2026-11-14 · refs: spike-plan §8, ADR-004*

The claims loop is built. Its parts:
- `domain/claims.py`: the ledger, a pure `step()` with ADD, AMEND, WITHDRAW and LINK, the 2-minute context
  window, and the digest shown to the extractor;
- `adapters/llm/openrouter_claims.py`: a strict JSON schema with one flat action object, parsed with pydantic;
  malformed actions are reported, not guessed;
- `app/claims.py`: the minute-by-minute replay, with every answer saved so a replay is free and deterministic;
- the end-of-event pass: the whole transcript plus the ledger. It adds what the live loop missed, links across the
  event, and withdraws duplicates and corrected claims. What it adds measures the live recall.

The extractor is `google/gemini-3.5-flash`. It takes about 15 s and costs about $0.03 per minute (about $1.70 per
hour), within the live budget.

Claims belong to voice labels (S1…N). Names attach later through names.json, never guessed. The names *inside* a
lekton are the people talked about, taken from what was said.

## K8

*done, 2026-11-14 · refs: ADR-004, ADR-008, [voices report](../eval/2026-11-14-voices.md)*

Diarization without a Hugging Face token: SpeechBrain ECAPA embeddings, with our own average-linkage clustering
(threshold 0.55) on CPU. About 25 s per hour of audio after the model download.

First results:

| event | main voices | other clusters |
|---|---|---|
| A | 3 (50 / 37 / 10 %) | 15 tiny ones under 20 s: cross-talk, overlap, jingles |
| B | 3 (43 / 37 / 16 %) | similar tiny ones |
| D1 | 3 (65 / 20 / 14 %) | 2 tiny |

Then:
- clusters under 1 % became "unclear" (A: 18 → 5 speakers; B: 21 → 4; C: 15 → 3; D1: 3; D2: 7 plus unclear);
- windows less than 0.30 similar to every speaker are "?";
- embeddings are cached (`embeddings.npz`);
- speaker changes snap to the largest word pause within ±1.5 s.

`lektyra voices` across the five events: one voice is in all five at 0.80–0.92 (studio 2022/2023/2025, parliament
hall, press room). The duel's second voice matches only itself. A's moderator = C's interviewer (0.87). Different
voices score ≤ 0.47. A threshold proposal is in the report.

Transcripts with speakers for all five events (`lektyra report`):
- A, B, C: about 10,000 words each, 1 word without a speaker;
- D2: 167 words without a speaker (the journalists' questions are off-mic).

## K7

*blocked:Martin, 2026-11-14 · refs: spike-plan §6, eval skill*

`lektyra compare` wrote one page per screening window (`data/events/<event>/compare-<from>-<to>.html`, next to
`audio.flac`). Every engine is side by side in 10 s rows. Words fewer than half of the other engines heard are
highlighted. A click on a time plays from there.

The templates in `data/refs/` are prefilled per row from the engine that agreed most with the others in that row:
a different engine per row, so the reference favours none. The quarter of rows with the most disagreement are marked
LISTEN: A 15/60, B 8/30, C 2/30, D1 1/30, D2 8/30. That is about 2 hours of listening in all.

## K5

*done, 2026-11-14 · refs: ADR-002, ADR-003, [report](../eval/2026-11-14-stt-screening.md)*

One adapter serves every OpenRouter transcription model: base64 FLAC, `verbose_json`, word and segment timestamps,
ZDR. On a refusal it asks again without timestamps or ZDR, and falls back to plain `json` for models that only
answer that. A 429 or 5xx is waited out (Retry-After or backoff, 5 tries). Answers are saved verbatim, with a
`.meta.json` holding cost, ZDR and timestamps. Failures go to `.error.json` and are retried on the next run.

Screening round: 11 models × 5 windows with `language=sk`, about $1.45. Top group by agreement: ElevenLabs, Gemini,
Grok, Voxtral.

Out:
- AssemblyAI: no language accepted through OpenRouter; auto-detect mishears Slovak;
- Chirp 3: fails on pieces over 60 s.

Zero data retention is not available for Gemini, Grok or the OpenAI GPT models. Gemini allows new accounts only
20 requests per minute. Found in the final round; the adapter now waits out 429s.

## K4

*next, 2026-11-14 · refs: spike-plan §2*

yt-dlp has no extractor for ta3.com. TA3's own player reads public templates from `embed.livebox.cz/ta3_v2/`:
- `vod-source.js`: the archive, HLS per video id;
- `live-source.js`: TA3 live;
- `nrsr-source.js`: the NR SR live stream TA3 carries.

The templates carry a short-lived signed token, so they are fetched fresh and never stored. An article page often
carries a teaser next to the episode. Article 902387 has only a 33 s teaser of A. The episode itself is on the
report article 902773 (video id `20230924-hw-c00bb050-bccf-4f30-9597-6ee24a85d5ae`, 3,429 s). The resolver probes
every embed and takes the longest.

Still to find:
- B: a 2022 Fico + Kollár duel; the article 255727 is a candidate;
- C: Fico's January 2025 interview, article 975381;
- D1: a parliament speech;
- D2: a government press conference.

## K3

*done, 2026-11-14 · refs: ADR-007*

Every source becomes 16 kHz mono s16le PCM from ffmpeg's stdout. Inputs:
- a TA3 page or `ta3:` address via `Ta3Resolver`;
- anything yt-dlp opens (`yt-dlp -o - | ffmpeg`);
- a direct media URL;
- a local file.

A multi-variant HLS playlist is read from its lowest-bitrate variant (`-map 0:p:<id>:a:0`), so no 1080p video is
downloaded for the audio. A stored video is read at decode speed: video A, 57 min, in about 2 minutes. Pieces and
the manifest are written as soon as each cut is made. Ctrl+C ends a live run and keeps the last piece. The manifest
holds no token-bearing URL (`media_url` is excluded).

The live path was proven on `ta3:live` (2026-11-14 13:09):
- 156.7 s of TA3's broadcast in 149 s of wall time, cut into 3 pieces as they arrived (pause, dip, end);
- `is_live: true`, no token in the manifest;
- one segment fetch failed mid-run ("Error reading HTTP response: End of file") and ffmpeg recovered. A long run
  needs reconnect handling (K15).

Found on the way: a Windows console in cp1252 crashed the run while printing "→" mid-stream. The CLI now writes
UTF-8.

## K2

*done, 2026-11-14 · refs: ADR-006 · asked for by Martin ("cutting voice should identify quiet moment")*

HTN's rule (pause ≥ 600 ms, forced at 90 s) is too strict for TV cross-talk. lektyra waits until 75 s are heard,
then takes the best quiet spot between 45 s and now:
1. the longest pause ≥ 250 ms, with a bonus for a speaker change;
2. else the deepest energy dip ≥ 120 ms, at least 10 dB under the median and not speech;
3. forced at 90 s.

Video A (57 min): 59 pieces of 46–75 s:
- 47 pause cuts, 11 dip cuts, **0 forced**;
- in the first 4 minutes, the 120 ms around each cut measured −60 to −65 dB, against a speech median of −27 dB
  (below even the quietest 10 % of frames, −52 dB).

Unit tests:
- replay = live: identical cuts for batch sizes 1, 31 and all;
- every piece between 45 and 90 s;
- `stitch` restores a word split by a forced cut.

Found on the way: 90 s is 2,812 frames = 89,984 ms, so a millisecond comparison never forced. Thresholds now
compare frames.

## K1

*done, 2026-11-14 · refs: ADR-001..007*

Repo created in Martin's personal space with a proprietary LICENSE from the first file. The spike plan and the
original concept (`concept.md`) live here; lektyra is a personal project (ADR-014).

Gates, modelled on HTN:
- `.githooks/lib.sh` holds rules L1–L8, each naming its ADR;
- `hook-tests.sh` has 21 cases, each rule seen to fire and to pass;
- shellcheck is clean;
- a post-edit guard runs ruff and mypy on each edited Python file;
- the full pre-commit run on all 63 files passes.

Tools installed with winget: uv 0.13.8, ffmpeg 9.0.2, yt-dlp 2026.10.26. They are on PATH in new terminals.

## K0

*done, 2026-11-14 · Martin*

Candidates checked:
- IntelliVoice: a live US mark, plus a VoIP company and the UK "Intelligent Voice" in speech-to-text;
- IntelliSpeech: a live US mark;
- IntelliDiscussion: clean, but narrow;
- Greek words: domains mostly taken;
- Rhemos: clean, but the US mark RHEMORIS (class 9) is close, and spoken it becomes "Remos".

lektyra won. A TMview/EUIPO and ÚPV search is still due before any commercial use.
