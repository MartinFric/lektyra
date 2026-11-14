# ADR-012: Every voice gets a number that continues across videos

*Status: accepted · 2026-11-14 · Martin ("any different profile increase the number … s2 as 2 different profiles on
2 different videos")*

## Context

Diarization labels speakers S1…N per video (ADR-008): S2 in one video and S2 in another are unrelated. Martin wants
every distinct voice to be one numbered profile everywhere: the same voice keeps its number in the next video, a
new voice gets the next number, and naming a number names that voice in every video.

## Decision

1. **An unnamed voice is a person row** with `anonymous = true`, a `number` from one sequence and the name
   `Voice <number>`. Named persons have numbers too; numbers are never reused.
2. **Every speaker gets a voice, oldest video first** (`Review.refresh_guesses`):
   - it sounds like a known voice, named or not (`decide` ≥ 0.70, ADR-004): it joins it (`auto`);
   - otherwise it **founds** the next voice from its own samples (`new`); the founder's samples define the voice;
   - a speaker with too little clean speech (fewer than 10 clean 2 s windows) stays unknown rather than found a
     voice from noise.
3. **Naming a speaker whose voice is unnamed names the whole voice:** the voice merges into the named person, who
   keeps the older (lower) number. Its samples, speakers and refusals move with it.
4. **"Not this voice"** is stored; the speaker is matched again without it and may found its own voice.
5. **Forgetting sticks** (ADR-005): a forgotten person's speakers are marked `no_profile` and never grow a new
   profile.
6. **A person is more than a name:** a kind (politician, host, journalist, expert, official, other), a key that never
   changes (UUID) for knowledge kept elsewhere, and a knowledge link (a Wikidata id or a URL).
7. Naming, re-matching and a live session's updates take turns behind one lock.

## Consequences

- A re-sync never renumbers. A video's first sync gives its new voices numbers in the order the videos were made.
- An automatic join is a guess (`auto`) until Martin confirms it; a merge from a wrong join is undone by removing
  the name and saying "not this voice".
- Founders' samples are `auto` provenance until a human confirms them.

## Enforced by

`tests/integration/test_review_api.py` (numbers across videos, merge keeps the number, refusal founds a voice,
forgetting sticks, kind/key/link), `migrations/0003_voice_numbers.sql`.
