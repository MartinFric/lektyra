# ADR-017: A mixed speaker is a label, never a voice

*Status: accepted · 2026-11-14 · Martin ("select type of voice not like person but combination and i can assign
multiple known persons to it", "this will be only tag", "we wont merge those mixed up voices into both profiles",
"mark it as mixed … it can be 2+ persons"; priority is always one person per voice)*

## Context

Diarization leaves small speakers where two people talk over each other (A S4 Fico + Kráľ, A S5 Kráľ + Kollár,
B S4 Dírer + Fico, C S3 Fico + Kráľ, the Kuffa clip's S6 Kráľ + Michelko). Such a stretch is nobody's voice: as a
profile it would sit between both people and pull matches the wrong way (K50). Naming it after one of them, as
was tried with C S3, teaches that person's voice the crosstalk.

## Decision

1. Martin can mark any speaker as **mixed**: two or more **named** persons talking at once (`speaker_overlap`,
   status `overlap`).
2. **A label only.** Marking takes back whatever samples the speaker gave a voice, gives none to anyone, founds no
   voice and is never matched; an unnamed voice left with nobody is removed. The people in it keep their voices as
   they were.
3. The transcript and every speaker list show "Fico + Kráľ" with both faces. Undo (×) makes it an ordinary speaker
   again, matched like any other; naming it after one person also ends the label.
4. Merging persons moves their place in a mixed label; forgetting a person drops them from it.

## Consequences

- Identity stays one person per voice. Mixed stretches may later serve as examples for overlap detection (K19,
  K50), never as identities.

## Enforced by

`migrations/0006_speaker_overlap.sql`; `tests/integration/test_review_api.py` (a label never a voice: samples taken
back, nobody's samples grow, re-sync leaves it alone, at least two, undo); `web/src/features/events/speakerName.test.ts`.
