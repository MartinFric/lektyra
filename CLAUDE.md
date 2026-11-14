# CLAUDE.md

Read [`AGENTS.md`](AGENTS.md) first: it holds every rule for agents in this repository, whatever the model.

Claude Code specifics:
- `.claude/settings.json` runs `.claude/hooks/post-edit-guard.sh` after every Edit/Write. It reports ruff/mypy
  findings for the file you just changed. The findings are advisory; the git hooks are the gate.
- The skills in `.claude/skills/` are the reference layer. Invoke the one that governs the code before writing it.
