#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
# Tests of the hook rules: every rule must be seen to fire, and to stay quiet on good input.
# Runs in a throwaway git repository; touches nothing here. Usage: bash .githooks/hook-tests.sh
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cd "$tmp" || exit 1
git init -q .
git config user.email t@example.invalid
git config user.name test
git config commit.gpgsign false

passed=0
failed=0

# expect <name> <expected blocks> <rule function> [args…]: runs one rule in a subshell, counts its blocks.
expect() {
  name=$1
  want=$2
  shift 2
  got=$(
    # shellcheck source=lib.sh
    . "$HOOK_DIR/lib.sh"
    "$@" 2>/dev/null
    echo "$LK_BLOCKS"
  )
  got=$(printf '%s\n' "$got" | tail -n 1)
  if [ "$got" = "$want" ]; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
    printf 'FAIL %s: expected %s block(s), got %s\n' "$name" "$want" "$got" >&2
  fi
}

stage() { # stage <path> <content>
  mkdir -p "$(dirname "$1")"
  printf '%s\n' "$2" >"$1"
  git add -f "$1"
}

reset_index() {
  git rm -rq --cached . >/dev/null 2>&1 || true
  rm -rf ./*
}

# L1 data guard
stage data/events/x/manifest.json '{}'
expect "L1 data/ is refused" 1 lk_rule_data "$(git diff --cached --name-only)"
reset_index
stage piece.FLAC 'not really audio'
expect "L1 audio by extension, any case" 1 lk_rule_data "$(git diff --cached --name-only)"
reset_index
stage src/lektyra/domain/x.py 'X = 1'
expect "L1 code passes" 0 lk_rule_data "$(git diff --cached --name-only)"
reset_index

# L2 size
mkdir -p big && head -c 1100000 /dev/zero | tr '\0' 'a' >big/blob.txt && git add big/blob.txt
expect "L2 over 1 MB is refused" 1 lk_rule_size "$(git diff --cached --name-only)"
reset_index
stage small.txt 'small'
expect "L2 small passes" 0 lk_rule_size "$(git diff --cached --name-only)"
reset_index

# L3 typing escape hatches
stage src/lektyra/app/a.py 'from typing import cast
x = cast(int, y)'
expect "L3 cast is refused" 1 lk_rule_typing "$(git diff --cached --name-only)"
reset_index
stage src/lektyra/app/b.py 'x: int = y  # type: ignore[assignment]'
expect "L3 type: ignore is refused" 1 lk_rule_typing "$(git diff --cached --name-only)"
reset_index
stage src/lektyra/domain/c.py 'from typing import Any
def f() -> Any: ...'
expect "L3 Any outside adapters is refused" 1 lk_rule_typing "$(git diff --cached --name-only)"
reset_index
stage src/lektyra/adapters/d.py 'from typing import Any
def f() -> Any: ...'
expect "L3 Any inside adapters passes" 0 lk_rule_typing "$(git diff --cached --name-only)"
reset_index
stage src/lektyra/app/e.py '"""Any source becomes a stream; podcast(x) is not a cast."""'
expect "L3 the word Any in prose passes" 0 lk_rule_typing "$(git diff --cached --name-only)"
reset_index

# L4 the domain is pure
stage src/lektyra/domain/f.py 'import subprocess'
expect "L4 I/O import in the domain is refused" 1 lk_rule_domain "$(git diff --cached --name-only)"
reset_index
stage src/lektyra/domain/g.py 'from lektyra.adapters.media import x'
expect "L4 adapter import in the domain is refused" 1 lk_rule_domain "$(git diff --cached --name-only)"
reset_index
stage src/lektyra/domain/h.py 'from datetime import datetime
NOW = datetime.now()'
expect "L4 the clock in the domain is refused" 1 lk_rule_domain "$(git diff --cached --name-only)"
reset_index
stage src/lektyra/domain/i.py 'import numpy as np
from lektyra.domain.audio import FRAME_MS
def reopen(x: int) -> int: return x'
expect "L4 a pure module passes" 0 lk_rule_domain "$(git diff --cached --name-only)"
reset_index

# L5 secrets: a token built at run time, so this file itself holds none
if command -v gitleaks >/dev/null 2>&1; then
  token="ghp_$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 36)"
  stage config.txt "github_token = \"$token\""
  expect "L5 a token is refused" 1 lk_rule_secrets
  reset_index
  stage notes.txt 'no secrets here'
  expect "L5 clean text passes" 0 lk_rule_secrets
  reset_index
else
  echo "SKIP L5: gitleaks not installed (the real hook blocks in that case)" >&2
fi

# L9 the UI's escape hatches
stage web/src/a.tsx '// eslint-disable-next-line no-restricted-syntax
useEffect(() => {}, []);'
expect "L9 eslint-disable in the UI is refused" 1 lk_rule_web_escapes "$(git diff --cached --name-only)"
reset_index
stage web/src/b.ts 'const x = y; // @ts-ignore'
expect "L9 ts-ignore in the UI is refused" 1 lk_rule_web_escapes "$(git diff --cached --name-only)"
reset_index
stage web/src/c.tsx 'export const ok = 1;'
expect "L9 clean UI code passes" 0 lk_rule_web_escapes "$(git diff --cached --name-only)"
reset_index
stage src/lektyra/app/j.py '# eslint-disable is only a word here'
expect "L9 Python is not the UI rule's business" 0 lk_rule_web_escapes "$(git diff --cached --name-only)"
reset_index

# L7 attribution, L8 subject
printf 'feat(ingest): read TA3 archive\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n' >msg
expect "L7 AI attribution is refused" 1 lk_rule_attribution msg
printf 'feat(ingest): read TA3 archive\n' >msg
expect "L7 a clean message passes" 0 lk_rule_attribution msg
printf 'updated stuff\n' >msg
expect "L8 a free-form subject is refused" 1 lk_rule_subject msg
printf 'fix(chunking): never cut inside a word\n' >msg
expect "L8 a conventional subject passes" 0 lk_rule_subject msg
printf 'Merge branch x\n' >msg
expect "L8 a merge passes" 0 lk_rule_subject msg

printf 'hook-tests: %d passed, %d failed\n' "$passed" "$failed"
[ "$failed" -eq 0 ]
