# K39: how many debate claims can public data settle? 2026-11-15

**Question:** what share of the claims made in Slovak political debates could be settled from public data, and
specifically from our own data service (K21: CRZ, NR SR votes and prints, company registers)? The market scan put
the line at about 10 %: below it, the data service is not much of a moat.

**Data:**
- five recordings, 3 h 58 min:
  - A: *V politike* 24. 9. 2023;
  - B: *V politike* 15. 5. 2022;
  - C: TA3 interview with the prime minister, 12. 1. 2025;
  - D1: NR SR question time;
  - D2: the government's drought press conference, Agrokomplex 2026.
- transcripts with Martin's names, guests only: hosts, the chair and journalists' questions are left out, and so is
  crosstalk;
- the claims:
  - A: the production extractor's 102 claims (`google/gemini-3.5-flash`, the replay of 2026-11-14);
  - B, C, D1, D2: extracted by Claude with the same rules (≈ 1.5–2 per minute of guest speech, promises kept as
    claims);
- judged by Claude, one subagent per video, with no web access. A claim is judged on whether a person with the data
  *could* settle it, not on whether it is true;
- the judged claims, each with class, dataset, confidence and reason, are kept locally in
  `data/eval/k39-2026-11-15/` (ADR-003, not committed).

**Classes:**

| class | settleable from |
|---|---|
| **K21** | CRZ; NR SR roll-call votes, prints, clubs, attendance; ORSR, RPVS, RÚZ/FinStat |
| **PUBLIC** | other official data: budget and Eurostat, ŠÚ SR, NBS, Slov-Lex, government resolutions, courts, ministry statistics |
| **OTHER** | only media archives of what someone said, non-public documents, witnesses |
| **NOT** | opinion, promise, prediction, too vague |

**Status:** a model's judgement, not Martin's. About half of the K21 calls are medium or low confidence. Read the
number as a range, not a point.

## Numbers

| video | claims | K21 | PUBLIC | OTHER | NOT | K21 + PUBLIC |
|---|---|---|---|---|---|---|
| A (Gemini's claims) | 102 | 13 (13 %) | 42 (41 %) | 39 (38 %) | 8 (8 %) | 54 % |
| B | 94 | 13 (14 %) | 28 (30 %) | 36 (38 %) | 17 (18 %) | 44 % |
| C | 94 | 12 (13 %) | 27 (29 %) | 34 (36 %) | 21 (22 %) | 41 % |
| D1 | 32 | 3 (9 %) | 14 (44 %) | 10 (31 %) | 5 (16 %) | 53 % |
| D2 | 72 | 2 (3 %) | 45 (62 %) | 12 (17 %) | 13 (18 %) | 65 % |
| **all** | **394** | **43 (11 %)** | **156 (40 %)** | **131 (33 %)** | **64 (16 %)** | **51 %** |

**The 330 checkable claims (all but NOT):**
- K21: 13 %;
- PUBLIC: 47 %;
- OTHER: 40 %.

**K21 by source:**
- NR SR: 33 (club sizes and membership, roll-call votes, bills and their stage);
- CRZ: 6;
- company registers: 4.

**K21 by confidence:**

| confidence | claims | of all | of the checkable |
|---|---|---|---|
| high | 19 | 4.8 % | 5.8 % |
| high or medium | 39 | 9.9 % | 11.8 % |
| any | 43 | 10.9 % | 13.0 % |

**What else would settle the PUBLIC claims (156, grouped roughly by keyword):**
- Eurostat and EU acts: about 30;
- government resolutions: 29;
- ŠÚ SR: 23;
- Slov-Lex: 20;
- ministry statistics: 13;
- courts: 6;
- other official: 32.

**K21 plus the three cheapest official sources** (government resolutions, Slov-Lex, ŠÚ SR) would settle 115 claims:
29 % of all claims, 35 % of the checkable.

## The answer

**K21 as planned sits right on the line: 11 % of all claims (5 % if only high-confidence calls count).** On this
sample, CRZ and the company registers alone are not a moat. NR SR carries K21: 33 of its 43 claims, mostly club
sizes and votes.

**Public data as a whole is a strong story: half of all claims, 60 % of the checkable.** The cheapest additions
roughly triple K21's reach. A third of all claims (OTHER) are "who said what when". The archive lektyra builds of
transcribed broadcasts is itself the source for many of those: our own data, not a scraped register.

**Recommendation:** go, with K21 re-scoped before building:
1. Keep NR SR first. It carries K21: club sizes over time, roll-call votes, prints and their stage. Add committee
   chairs and question time, which several claims needed.
2. Add government resolutions and Slov-Lex next. Both are cheap and official, and on this sample they are worth more
   than the company registers.
3. Add ŠÚ SR (DATAcube), then Eurostat.
4. Keep CRZ and the registers, and measure again on a procurement or corruption debate. None of the five videos is
   one, so this sample under-counts them.
5. The quote archive (K37's statement table plus our transcripts) settles "X said Y on date Z" claims. That is the
   biggest class here after PUBLIC.

## Caveats

- **Topic skew:** the five videos are about the prosecutor-general affair, migration, Ukrainian grain, gas transit,
  rule of law and drought aid. Contracts and companies barely come up. One procurement debate would move K21
  noticeably.
- **Speaker skew:** Robert Fico makes 271 of the 394 claims (69 %).
- **Two extractors:** NOT is 8 % in A against 19 % in B–D. Gemini drops more opinion, while Claude kept promises and
  predictions as claims. K21's share of the checkable claims is similar in both (14 % and 13 %).
- **NR SR depth:** several claims need votes from 2003 (Iraq, the EU referendum) or documents from 2011–12. K21 has
  to go back that far, or those claims stay unsettled.
- **Judged, not checked:** nobody fetched the records. "Could be settled" assumes the record exists as expected. For
  example, a CRZ call assumes the contract is published in CRZ.

## What the judging found in the production extractor (feeds K60)

Found on A, Gemini's 102 claims:
- **Wrong speaker (3 claims):** two host lines were given to Fico. One of Kollár's lines was given to Fico, which
  reverses who is accusing whom.
- **Placeholders leak:** "S1" and "S2" appear inside 4 lektons. The replay ran before the names were set.
- **Added facts:** some lektons add names or years the speaker never said (Faeser, Orbán, 1989, Trianon, Fun rádio).
  A check would then test the extractor, not the speaker.
- **Duplicates:** 1 exact, 1 near. The end pass should have linked them.
- **Source tags:** `media` is on 84 of 102 claims and means little. `statistics` is reliable (14 of 15 are PUBLIC).
- **`worth` does not follow checkability:** the top-worth claim (1.0), that two NGOs kept silent, cannot be settled
  from data.
- **Missed:** 2 claims K21 could settle (NGOs living off the state budget; Kollár's radio in public tenders).
