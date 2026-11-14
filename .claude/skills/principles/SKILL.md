---
name: principles
description: lektyra's ranked rules and how to decide when two collide. Read before writing or changing any code in this repository.
---

# Principles (ranked: a higher rule wins a collision)

1. **Data stays local** (ADR-005). Audio, video, embeddings, model answers and keys never enter git, never get
   printed, never leave the PC except as speech-to-text requests. When unsure whether something is data: it is.
2. **A wrong name is worse than "unknown"** (ADR-004). Speaker identity, claim attribution and verdicts err toward
   "unknown" or "needs a human". Never guess a person.
3. **Replay = live** (ADR-007). There is one path. A recorded video run is a test of the live run; a shortcut that
   works only for files is a bug.
4. **The domain is pure** (ADR-002). Logic lives in `src/lektyra/domain/` with no I/O and no clock, and is
   unit-tested there. Adapters only translate; `app/` wires; `cli.py` only parses and prints.
5. **Types are proven, not asserted** (ADR-001). mypy strict; data is parsed at the boundary (pydantic); no `cast`,
   no `type: ignore`, no `Any` outside adapters.
6. **Paid answers are kept** (ADR-003). Never pay twice for the same audio; never evaluate from memory.
7. **Words are never cut** (ADR-006). Cuts go in quiet moments; overlap and stitching cover the rest.
8. **Measure, don't assume.** A claim about quality (WER, DER, profile hits, cut quality) comes with a number from
   a report in `docs/eval/`.

## When two rules collide

Take the higher rule, and write down why in the board's detail entry. If a rule is wrong, change its ADR first (a
new ADR that supersedes it), then the code. Never weaken a hook to make a commit pass.

## Small things that matter

- Errors say what to do next ("yt-dlp cannot open X: … try ta3:<id>"), not just what failed.
- Slovak text is normal input: names with diacritics, `→` in output. Never assume ASCII or cp1252.
- Time is passed in, never read inside the domain: `now: Callable[[], datetime]` at the edge.
