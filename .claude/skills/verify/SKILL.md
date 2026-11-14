---
name: verify
description: lektyra's numbered verification checklist to run before saying work is done or asking Martin to commit. Use at the end of any change.
---

# Verify (run all; report each as pass/fail with its output)

1. `uv run ruff check .` and `uv run ruff format --check .`: clean.
2. `uv run mypy`: "Success", strict.
3. `uv run pytest -q -m "not slow"`: all pass. Then `uv run pytest -q` if Postgres or ffmpeg code changed.
4. `bash .githooks/hook-tests.sh`: all pass. Then `shellcheck -x .githooks/* .claude/hooks/*.sh`: clean.
5. **The guard can fire**: for a new hook rule, a test case where it blocks, not only one where it passes.
6. `git status --short`: nothing under `data/`, no audio, video or model file, nothing > 1 MB staged or untracked
   outside `.gitignore`.
7. **No secrets in output**: the change prints no key, token-bearing URL or embedding. Check new `print`/log lines
   and saved JSON (`SourceInfo.media_url` stays excluded).
8. **Docs move with the code**: board row updated (state, date, evidence); an ADR changed if a rule changed;
   AGENTS.md if a command changed.
9. **A real run** for anything touching ingest or engines: run it on a short TA3 sample (`--max-minutes 2`) and
   quote the output.
10. Report what was **not** verified, plainly.
