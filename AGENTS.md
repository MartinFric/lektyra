# AGENTS.md

Any coding agent working in this repository, whatever model it runs on, reads this first. `CLAUDE.md` points
here; nothing in it is Claude-specific.

**lektyra** turns a live stream or a stored video into a transcript, finds who speaks, recognises known voices,
and extracts the statements worth checking (the *lekton*: what is said, the part that can be true or false). It is
standalone, runs locally and is written in Python.

## Where things are

- **Decisions**: `docs/adr/`. An ADR wins over instinct and over the plan. A new decision is a new ADR (skill
  `architect`).
- **In flight**: `docs/plans/board.md`, with detail by id in `docs/plans/detail.md` (Martin's board convention).
  The board moves in the same commit as the work.
- **The plan**: `docs/plans/spike-plan.md`.
- **Skills**: `.claude/skills/`. Read the one that governs the code you touch before you write:
  - `principles`: always;
  - `architect`: where code goes;
  - `stt-engine`: speech-to-text adapters;
  - `voice-profiles`;
  - `eval`;
  - `privacy`: always, before touching data;
  - `testing`;
  - `frontend`: anything under `web/` or the review API (ADR-009);
  - `manual-testing`: after a UI change, walk it with screenshots before saying it works;
  - `verify`;
  - `commit`;
  - `review`.

## Rules that are never negotiable

- **No git writes** (commit, push) unless Martin asks. **No AI attribution** in commits; `commit-msg` refuses it.
- **Never in git**: audio, video, voice embeddings, anything under `data/`, keys. A hook refuses them (ADR-005).
  **Never print a key**: settings hold them as `SecretStr`.
- **Typing**: `mypy --strict`. No `cast()`, no `# type: ignore`, no `Any` outside `src/lektyra/adapters/`. Data is
  parsed where it enters (pydantic) (ADR-001).
- **The domain is pure**: `src/lektyra/domain/` does no I/O and imports nothing from `adapters/` or `app/`
  (ADR-002).
- **A wrong name is worse than "unknown"** (ADR-004).
- **The UI** (`web/`): no casts, no non-null `!`, no `any`, no `useEffect`, no raw `fetch`, no `eslint-disable` or
  `@ts-ignore`; ESLint and hook L9 refuse them (ADR-009, skill `frontend`).

## The gates

Git hooks in `.githooks/` are model-agnostic plain bash, activated by
`git config core.hooksPath .githooks`. `git commit` runs them. Read what they say: each rule names its ADR.
- Their own tests: `bash .githooks/hook-tests.sh`.
- Escape hatch: none. Fix the cause or change the ADR first.

## Running

```
uv sync                         # Python 3.12 environment from uv.lock
uv run lektyra doctor           # tools, keys (present or not, never their value), database
uv run pytest -m "not slow"     # fast tests
uv run mypy                     # strict
uv run ruff check . && uv run ruff format --check .
docker compose up -d            # local Postgres 17 + pgvector on 127.0.0.1:55432
bash .githooks/hook-tests.sh    # the hooks' own tests
uv run pytest                   # all tests, the API integration test too (needs Postgres)
```

The review UI (ADR-009): build once, then serve. Node 24 via fnm (`eval "$(fnm env --shell bash)"`).

```
cd web && npm ci && npm run build && cd ..   # web/dist; `npm run check` = typecheck + lint + tests
uv run lektyra ui                            # http://127.0.0.1:8765 — migrates, syncs data/events, serves
cd web && npm run dev                        # while working on the UI: 5173, /api proxied to 8765
uv run lektyra ui --database lektyra_manual --reset --port 8799   # throwaway copy for skill manual-testing
```

Ingest takes any source (ADR-007):
- a TA3 article (the longest video on the page) or `ta3:<video id>`;
- `ta3:live` and `ta3:nrsr` (parliament);
- anything yt-dlp opens (YouTube, …);
- a direct `.m3u8` or `.mp4`;
- a local file.

```
uv run lektyra ingest "https://www.ta3.com/clanok/902773/x" --title "A V politike 2023-09-24"
uv run lektyra ingest ta3:live --max-minutes 5          # Ctrl+C ends a live run; the last piece is kept
uv run lektyra ingest some.mp4 --realtime               # replay a file at live speed
```

Output: `data/events/<time>_<title>/` with `audio.flac`, `pieces/NNNN.flac` and `manifest.json`.

Then:

```
uv run lektyra catalog                                   # OpenRouter speech-to-text models and prices today
uv run lektyra transcribe a-v-politike --window 20:00-30:00 --language sk            # screening set (11 models)
uv run lektyra transcribe a-v-politike --language sk --models elevenlabs/scribe-v2   # one model, whole event
uv run lektyra compare a-v-politike --window 20:00-30:00  # side-by-side page + reference template (data/refs/)
uv run lektyra diarize a-v-politike                      # S1…N, turns, speakers.md for naming
uv run lektyra voices                                    # match speakers across events by voice alone
uv run lektyra report a-v-politike                       # transcript with speakers (names from names.json, if any)
uv run lektyra claims a-v-politike                       # the live claims loop, replayed minute by minute
uv run lektyra end-pass a-v-politike                     # the whole-picture review: missed claims, links, duplicates
```

Results so far: `docs/eval/` (screening, voices).

An event is named by its folder, its id, or any unique part of the id.

Keys live in `~/.secrets/lektyra.env` (`OPENROUTER_API_KEY`, `SONIOX_API_KEY`, `HF_TOKEN`). Never in the repo.
