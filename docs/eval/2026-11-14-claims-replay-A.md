# Claims loop replay on video A, 2026-11-14

**Question:** does the live claims loop (spike-plan §8) produce checkable claims, in time, at a sane cost? And does
the end-of-event pass add what the live loop missed?

**Data:**
- video A (*V politike* 24.9.2023, 57 min, three voices);
- transcript: `elevenlabs/scribe-v2@sk` on the diarization's turns (S1…N, no names);
- extractor: `google/gemini-3.5-flash`, strict JSON schema;
- replayed minute by minute exactly as live: the new minute, 2 minutes of context, and the ledger digest;
- answers saved under `data/` (ADR-003).

**Status:** a prototype. Quality without Martin's gold set (K20) is judged by eye and by one manual check.

## Numbers

| | |
|---|---|
| minutes replayed | 57 |
| claims (live) | 114 (≈ 2 per minute) |
| time per minute | mean 12.7 s, max 25.7 s: inside the 60 s a live run has |
| cost | live $1.75 (≈ $1.85 per hour of broadcast) + end pass $0.15 |
| malformed actions | 3, reported and skipped (e.g. a link without its target), never guessed |
| rejected actions | 1 (an id that does not exist) |
| end pass | **+1 claim missed live**, 8 links, 2 withdrawn as duplicates, 0 amended |
| live recall vs the final ledger | 99 %. This is self-consistency: the same model reviewed its own ledger. The real recall needs the gold set |

## What the claims look like

Each lekton is one self-contained Slovak sentence with the subject resolved from context. Kinds and sources are
plausible:
- law: Article 107 of the Constitution (three-fifths majority) → `nrsr`;
- contract: a monitoring contract of the caretaker government → `crz, finstat`;
- numbers: grain production versus consumption → `statistics`.

The links catch what an editor wants:
- "180 % of consumption" (S2) linked to "about twice as much" (S1): related, and not quite the same;
- an army-size figure linked as *contradicting* a later one;
- a promise linked as *supporting* the earlier announcement it fulfils.

Weak spots:
- `kind` is often `other`;
- `worth` is generous: 0.7–0.9 for many claims;
- a few lekton sentences are background the moderator states, not a politician's claim.

Speakers are voice labels. The names inside a lekton are the people talked about, taken from what was said.

## One claim checked by hand against CRZ (the step K21 automates)

Claim c23 (A, 09:35, S1): a company received a social-media monitoring contract worth "416 thousand euros" from the
caretaker government.

Two read-only CRZ queries (supplier, then the framework agreement's number) give:
- framework agreement SE-VO1-2023/002645-013, signed 14.9.2023, inside that government's term;
- €499,500 at the Ministry of Foreign Affairs, plus a €67,500 call-off at the Government Office;
- ended 28.5.2024.

€499,500 / 1.2 = **€416,250**: the claim quotes the price without VAT. **Draft verdict: true, the amount excludes
VAT.** The ownership part of the claim needs finstat and is unchecked.

## Decision (provisional)

- The loop works live: under 26 s per minute, about $1.85 per hour.
- Keep the end-of-event pass. It is cheap and it finds duplicates and links across the event. Its "missed" count
  only means something with a different model or the gold set.
- Next:
  - the gold set (K20);
  - a stricter `worth` (calibrated on the gold set);
  - quick checks against lektyra's own public-data service for contract/amount, company and vote (K21, ADR-014),
    which turn the CRZ example above into code.
