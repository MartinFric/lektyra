# ADR-006: Audio is cut in quiet moments, never inside a word

*Status: accepted · 2026-11-14 · Martin ("cutting voice should identify quiet moment — not cutting the words")*

## Context

Audio goes to speech-to-text in pieces of about a minute (live latency, API limits). A cut inside a word loses or
garbles that word in both pieces. HTN's recorder cuts at a pause ≥ 600 ms, forced at 90 s. That works for
per-speaker push-to-talk audio. A TV debate has cross-talk and music beds and rarely pauses for 600 ms, so HTN's
rule would often end in its forced cut.

## Decision

`domain/chunking.choose_cut` decides, from a speech-probability curve (Silero VAD, 32 ms frames of 512 samples) and an energy curve:

1. Nothing is decided until **75 s** are heard. Then the **best** spot between **45 s** and what has been heard is
   chosen, not the first.
2. First choice is the longest run of silence of at least **250 ms**. Broadcast speech pauses 200–400 ms between
   sentences. A speaker change inside the run gives a bonus.
3. If there is no pause: the deepest energy dip of at least **120 ms**, meaning frames in the window's quietest 15 %
   and at least **10 dB** under its median, whose least speech-like frame has speech probability ≤ 0.5. Micro-pauses
   fall between words, never inside one. The cut lands on that frame.
4. At **90 s** a cut is forced at the quietest frame between 45 and 90 s. A pause is cut in its middle.
5. **Overlap**: every piece starts **1.5 s** before the previous cut. With word timestamps, a word in the overlap is
   taken from the piece where it lies further from the edge (`stitch`).

## Consequences

A piece ends up between 45 and 90 s long, and live latency stays near one minute. Engines without word timestamps
can only be stitched by text, which is weaker.

## Enforced by

Unit tests of `choose_cut` and `stitch` on synthetic curves; the eval metrics "words cut" (must be 0) and "WER in the
3 s around cuts vs elsewhere".
