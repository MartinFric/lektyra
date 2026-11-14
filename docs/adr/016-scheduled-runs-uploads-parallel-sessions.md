# ADR-016: Scheduled live runs, uploaded videos played as live, several sessions at once

*Status: accepted · 2026-11-14 · Martin ("schedule run for at least stvr and ta3 streams", "only 3 really live
things - with possibility to play uploaded video as live … uploaded to minio … with possibility to delete it",
"live stream - configured for ta3 stvr and facebook - youtube", "i need to see list of scheduled and list of
transcribed videos"; tonight, parallel runs included; Facebook public only)*

## Context

Sunday's shows overlap (TA3 until about 12:00, STVR from 11:55), and Martin wants lektyra to start and stop them on
its own. ADR-013 allowed one session per `lektyra ui` (a second UI on another port for overlaps). The Live screen
listed whatever files happened to be in `data/videos/`.

## Decision

1. **Several sessions in one `lektyra ui`** (at most 4), each with its own id, threads and voice model. Voice
   updates take turns behind the review lock and the advisory lock (ADR-012 point 7), so two sessions never found
   the same voice twice. One session per PC sound output. Supersedes ADR-013 §1.
2. **Sources** are what a session can open, never a path on the PC: the three live channels (TA3 `ta3:live`, STVR
   Jednotka `stvr:1`, STVR Dvojka `stvr:2`), a public **YouTube or Facebook** address (yt-dlp; no browser cookies),
   **this PC's sound**, or an **uploaded video** (`upload:<id>`).
3. **Uploaded videos** are kept in lektyra's MinIO (bucket `lektyra-videos`, `videos/<id>/<name>`), listed in
   `video_upload`, and played as live: the UI plays the file while lektyra hears it at the same speed. A working
   copy lives in `data/cache/uploads/` and is fetched again when it is gone. Delete removes the row, the object and
   the copy; it is refused while a session plays it or a scheduled run needs it. `lektyra fetch` keeps what it
   downloads as an upload. Research use only (ADR-005).
4. **Scheduled runs** (`scheduled_run`): a source, a title, from–to (at most 6 hours, at most 60 days ahead). A
   thread in `lektyra ui` checks every 5 s: a run starts at its time (late, if lektyra was not running then, while
   its time lasts), stops at its end, and points at the video it became. A run whose session fails before its end
   (a dropped stream) starts again, at most 3 times; a run whose whole time passed while lektyra was off is
   *missed*; one that was running when lektyra stopped starts again for the time left. What to do when is a pure
   function (`domain/schedule.py`).
5. **Every database has its own buckets** (`lektyra-pictures`, `lektyra-videos` for the main one,
   `…-<database>` for any other): a test database never sees, or sweeps, the real files (found tonight: a
   rehearsal on `lektyra_manual` swept the main pictures; they were restored from Commons).
6. **The Live screen** shows the sessions as tabs, *Start now*, the scheduled runs (to come, running, what ran and
   its video) and the latest transcribed videos.

## Consequences

- The PC must be on and awake with `lektyra ui` running for a run to start; the UI says so.
- Each session costs a voice model in memory (~90 MB) and its share of the CPU; 4 at once is the cap.
- Facebook pages that need a login do not open; adding browser cookies is a later, deliberate decision.

## Enforced by

`migrations/0005_schedule_and_uploads.sql`; `tests/unit/test_schedule.py`, `test_buckets.py`;
`tests/integration/test_scheduler.py` (on time, stop at the end, the video, a dropped stream, missed, late);
`tests/integration/test_review_api.py` (uploads, refusals, schedule API, source guards); rehearsed 2026-11-14:
TA3 and STVR scheduled side by side, an upload played as live after its local copy was removed.
