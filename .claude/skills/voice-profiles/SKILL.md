---
name: voice-profiles
description: lektyra's voice profiles: persons, samples, matching (k-NN + score normalisation), rebuild from samples, rejections, forget, thresholds. Use before touching speaker identification, profiles or the person tables.
---

# Voice profiles (ADR-004, biometric data under ADR-005)

## Model

- `person`: name, function, party, public-figure flag.
- `voice_sample`: one clean stretch of one person, with the event and times, `embedding`, `embedding_model`,
  provenance (`auto` / `human_confirmed` / `human_corrected`), quality and weight.
- `voice_profile`: derived; sample counts and channels seen. Centroids only as a cache.
- `event_speaker`: S1…N of an event, its embedding, best match, and status `auto` / `suggested` / `unknown` /
  `confirmed`.
- `voice_rejection`: "event speaker X is NOT person P".

## Rules

1. **A profile is a function of its samples.** Rebuild it, never patch it. Undo = delete samples, then rebuild.
   A new embedding model means re-embedding the stored clips, then rebuilding.
2. **Match against the k nearest confirmed samples**, after adaptive s-norm against a cohort of other speakers. One
   threshold then holds across channels (studio, hall, phone). Do not create profiles per channel or quality.
3. **Quality is a gate and a weight**: no overlap with another voice, at least a few seconds, enough SNR.
4. **Auto samples** feed a profile only above a high score and with a low weight, so a profile never drifts on its
   own guesses.
5. **A human naming Person X**: their clean segments become `human_confirmed` samples, then rebuild, then re-match
   the unknown speakers of past events as *suggestions*.
6. **A human correcting a wrong match**: write a rejection, remove that event's auto samples from the wrong
   person, then rebuild both.
7. **Thresholds**: set from the score distributions in the profiles report, for **zero false names first**.
   Statuses: ≥ accept → `auto` (still shown to the reviewer); suggest–accept → `suggested`; below → `unknown`.
8. `forget "<person>"` deletes the person, samples, profile and clips, and leaves an audit entry with no biometric
   content.

## Tests

- Rebuild is deterministic (same samples → same profile).
- A rejected pair is never matched again.
- Forget leaves nothing.
- Synthetic embeddings only: never real voices in tests.
