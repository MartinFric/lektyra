# ADR-013: A live session: voices now, words a piece behind

*Status: accepted · 2026-11-14 · Martin ("run the video … inside UI so i can actually hear the voice and match the
person … as it is live stream")*

## Context

Sunday's debates run live; Martin wants to hear a voice and name it while it speaks. The offline diarization sees
the whole video before it clusters; live cannot wait. A downloaded video played at live speed must behave exactly
like a stream (ADR-007), so rehearsals are honest.

## Decision

1. *(Superseded by ADR-016: several sessions run in one `lektyra ui`.)* **One session per `lektyra ui`**; several can run side by side on other ports (`--port 8766`), on the same
   database and the same voice numbers. Voices are written by one process at a time (a Postgres advisory lock, held
   while matching founds or joins voices), so two sessions never found the same voice twice. Tested: TA3 and STVR
   live at once, 0 orphaned voices. Each session is owned by its `lektyra ui`. Source: a file in `data/videos/` (from `lektyra fetch`: TA3,
   YouTube, Facebook; 720p, copied, not re-encoded) or a stream address (`ta3:live`, https://…). Always read at live
   speed.
2. **Voices now** (`domain/live_voices.py`): every second, the last 2 s, if at least 60 % of it is speech, is
   fingerprinted (ECAPA, ADR-008) and given to a session speaker online: it joins the closest speaker at cosine
   ≥ **0.40**; windows close to nobody wait, and **5** that agree found a new speaker; stragglers stay unclear.
   Calibrated by replaying the five spike videos' windows in order against their offline diarization: purity
   ≥ 0.97, no main voice split, 4–13 live speakers against 3–8 offline (the extras are short fragments).
3. **Numbers and names as for archives**: every 5 s the session writes the files diarization writes
   (`diarization.json`, `speakers.npy`, `embeddings.npz`, each replaced whole) and lists the speakers heard for at
   least 8 s, so they get a voice number or a name (ADR-012), and Martin names them while they speak.
4. **Words a piece behind**: live pieces are shorter (cut from 20 s, decided by 30 s, forced at 40 s; ADR-006's
   rule with smaller numbers) and each goes to speech-to-text in the background (ElevenLabs Scribe v2, Slovak).
5. **The UI plays the downloaded video next to lektyra**: the player starts at lektyra's position; the drift is
   shown and one click syncs it. A live stream is watched on TV; the screen shows who speaks and the words.
6. When the session ends, the event is an ordinary video: speakers, names, transcript, ratings.
7. **A channel that only plays in a protected player** (Orange TV in the browser, DRM) is heard through **the PC's
   sound output** (`pc:sound[:device]`, Windows WASAPI loopback, 48 kHz → 16 kHz through a low-pass filter). Nothing
   is decrypted or downloaded: lektyra hears what the PC plays, so other sounds must be off. Circumventing the
   player's protection is not an option (copyright law protects it on its own, whatever the subscription).
   Whether recording a subscribed channel this way is allowed for analysis is part of the legal opinion (K40).

## Consequences

- "Speaking now" lags speech by about 2–3 s; words arrive 30–60 s after they are said.
- Live speakers are fewer-merged than offline ones: a voice can appear as two numbers until a name merges them.
- A session costs about $0.22 an hour for words; voices are free (CPU).

## Enforced by

`tests/unit/test_live_voices.py` (turns, founding after 5 windows, noise stays unclear, windows due only on speech),
`tests/integration/test_review_api.py` (live guards), the manual-testing walk of the Live screen.
