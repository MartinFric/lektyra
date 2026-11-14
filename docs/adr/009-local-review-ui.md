# ADR-009: A local review UI — React on a small JSON API, decisions in the database

- **Status:** accepted (2026-11-14)
- **Context:** Martin names speakers, rates transcripts and flags mistakes; Sunday's live runs need naming while a
  stream plays. Files (`speakers.md`, `names.json`) were enough for one video, not for five, and not for live.

## Decision

1. **A local web UI**, served by `lektyra ui` on 127.0.0.1 only: FastAPI with a JSON API under `/api`, and the
   built React app (`web/dist`) for every other path. No login: it never leaves the PC (ADR-005).
2. **Files stay the source of audio, words and diarization**; the database holds **what Martin decides** (persons,
   names, rejections, ratings, flags) and the voice samples his names produce. `lektyra ui` migrates the
   database and syncs `data/events/` on start; **Rescan folders** syncs again. A re-sync never touches a name.
3. **Naming is the learning step (ADR-004):** naming a speaker turns its clean windows into ~20 s samples of that
   person (`profile_samples`), replacing what that speaker gave before; then every unnamed speaker in every video
   is matched again (`decide`: k nearest samples vote; ≥ 0.70 *auto*, ≥ 0.55 *suggested*). A guess is shown as a
   guess until Martin confirms it; "Not X" is stored and X is never suggested for that speaker again. Forgetting a
   person deletes their samples and names (ADR-005).
4. **Frontend stack:** React 19, TypeScript strict, TanStack Query, React Router, zod at the boundary, sonner for
   toasts, CSS Modules on design tokens; one API wrapper and one error model (`AppError`). Rules in skill
   `frontend`, enforced by ESLint and hook L9 (no casts, no non-null, no `any`, no effects, no raw fetch, no
   disable comments).
5. **One error shape** from the API: `{"error": {"code", "message", "details"}}`, codes `not_found`, `conflict`,
   `invalid`, `unavailable`, `internal`. Messages are for Martin and carry no key, path or voice.
6. **UI checks are manual walks with screenshots** (skill `manual-testing`: a separate database `lektyra_manual`,
   headless Edge, every shot read back) plus Vitest for pure logic and an API integration test. No end-to-end
   suite: for a one-person local tool the walk is faster to keep true.

## Consequences

- Schema 0002: `person.note`, unique names, `event_speaker` unique per (event, run, label) with talk time and
  share, `transcript_rating`, `transcript_flag`, more audit actions.
- Two databases on the local server: `lektyra` (Martin's) and `lektyra_manual` (throwaway, may be reset).
  Tests use a third, `lektyra_test`.
- If diarization is re-run and labels shift, a stored name may point at a different voice; re-running diarization
  on a named event must re-check names first (open, K9).
- Node 24 + npm are needed to build the UI; the built `web/dist` is not committed.
