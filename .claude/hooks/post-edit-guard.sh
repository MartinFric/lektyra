#!/usr/bin/env bash
# Claude Code PostToolUse hook: after an Edit/Write of a Python file, run ruff and mypy on it.
# Advisory: it cannot undo the edit. Findings go to stderr with exit 2 so the session that wrote the code sees
# them while the reasoning is still in context. The git hooks are the gate (AGENTS.md).
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || echo .)}" || exit 0

payload="$(cat)"
# file_path without jq (not guaranteed on Windows); backslashes become slashes.
file="$(printf '%s' "$payload" | tr ',' '\n' | grep -m1 '"file_path"' |
  sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//; s/".*//; s/\\\\/\//g')"
[ -n "${file:-}" ] || exit 0
case "$file" in
  *.py) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0
command -v uv >/dev/null 2>&1 || exit 0

out="$(uv run --quiet ruff check --output-format concise "$file" 2>&1)" || {
  printf '[lektyra-guard] ruff findings in %s:\n%s\n' "$file" "$out" >&2
  exit 2
}
out="$(uv run --quiet mypy "$file" 2>&1)" || {
  printf '[lektyra-guard] mypy --strict findings in %s:\n%s\n' "$file" "$out" >&2
  exit 2
}
exit 0
