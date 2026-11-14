# ADR-011: Ad breaks pause the analysis; listening continues

*Status: accepted · 2026-11-14 · Martin ("we need to be able to identify advertisements and just pause everything
during them – they may and may not occur")*

## Context

Commercial channels (Markíza, TA3, JOJ) break discussion shows for ads. Ad audio would pollute everything:
- claims from ad copy;
- voice samples from voice-over artists in someone's profile;
- speaker turns of nobody.

Breaks may or may not come, and their length varies.

## Decision

- **Signals**, combined per piece and per few seconds:
  1. **no expected voice**: none of the show's expected profiles (ADR-004) matches, and voices change fast;
  2. **music**: high energy with low speech probability over seconds (Silero + energy, already computed per frame);
  3. **the words**: the piece's transcript reads like an ad (brands, prices, "kúpte", "akcia"). This is a cheap text
     classification inside the minute's extraction call;
  4. **jingles**: the channel's break-in and break-out jingles, learned as audio fingerprints from recordings, once
     we have them.
- **During a break: listening continues, analysis pauses.**
  - Audio is still recorded and transcribed. That is cheap, and it is needed to hear the show return.
  - The stretch is marked `ad` in the manifest and transcript.
  - It produces no claims, no voice-profile samples and no speaker attribution.
  - The UI shows "Ad break · paused".
- **When unsure**, the stretch is marked `possible ad`. A human can flip it either way, and the analysis of that
  stretch reruns from the saved answers.
- **The show is back** when an expected voice matches again, or the break-out jingle plays.

## Consequences

A short ad-like stretch inside the show (a guest naming a product) may be marked `possible ad`. That is visible and
reversible. Nothing is deleted.

## Enforced by

`domain/adbreak.py` (pure: combines the signals into a state machine with hysteresis, tested on synthetic
sequences); the replay of a recorded show with a known break; review.
