---
name: review
description: How to review a lektyra change: the lenses greps cannot catch (identity errors, replay≠live, data leaving the PC, cost, Slovak text) and a refute pass. Use when asked to review a diff or before a larger commit.
---

# Review

Read the diff against the ADRs. Report findings as `file:line`: what is wrong, the scenario where it fails, and
the fix. Then try to **refute each finding**. Keep only those that survive.

## Lenses

1. **Identity and verdicts** (ADR-004). Can this name the wrong person or attribute a claim to the wrong speaker?
   Does anything turn "unknown" into a guess? Are thresholds from a report?
2. **Replay = live** (ADR-007). Does behaviour depend on how frames arrive, on the source type, or on reading ahead
   in a stored file?
3. **Data leaving** (ADR-005). New network calls, logs, saved JSON, exceptions with URLs or keys, fixtures with real
   voices.
4. **Cutting and timing** (ADR-006). Off-by-one between ms, samples and 32 ms frames. Overlap applied twice or not
   at all. Piece-relative vs stream time.
5. **Money** (ADR-003). Can it pay twice for the same audio, or call an API in evaluation?
6. **Types at the boundary** (ADR-001). Is outside data parsed (pydantic), or trusted?
7. **Slovak reality.** Diacritics, `→`, cp1252 consoles, names with titles (Ing., JUDr.), numbers written as words.
8. **Failure modes.** A live stream dropping, ffmpeg dying, a 429 from an engine, Ctrl+C mid-piece. Is the
   manifest still valid? Is the last piece kept?
