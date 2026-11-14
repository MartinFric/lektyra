#!/usr/bin/env bash
# lektyra hook rules: sourced by pre-commit, commit-msg and hook-tests.sh. Each rule names its ADR.
# Model-agnostic, plain bash 3.2 (macOS default): no mapfile, no associative arrays.
#
# Rules scan the STAGED content (git show :path), so `git add -p` cannot smuggle a violation past them.
#   L1 data guard            ADR-005   L5 secrets (gitleaks)           ADR-005
#   L2 file size > 1 MB      ADR-005   L6 ruff, ruff format, mypy, pytest ADR-001
#   L3 typing escape hatches ADR-001   L7 no AI attribution (commit-msg) AGENTS.md
#   L4 the domain is pure    ADR-002   L8 conventional subject (commit-msg)
#   L9 the UI (web/): no lint/type escape hatches, then typecheck, lint, tests   ADR-009

LK_BLOCKS=0
LK_MAX_BYTES=1048576

lk_block() {
  printf 'BLOCK [%s] %s\n' "$1" "$2" >&2
  LK_BLOCKS=$((LK_BLOCKS + 1))
}

# Staged paths (added, copied, modified, renamed), one per line.
lk_staged() {
  git diff --cached --name-only --diff-filter=ACMR
}

# Lines this commit adds to a staged file, without the leading '+'.
lk_added_lines() {
  git diff --cached -U0 -- "$1" | grep '^+' | grep -v '^+++' | sed 's/^+//'
}

# L1 (ADR-005): audio, video, embeddings, models and anything under data/ never enter git.
lk_rule_data() {
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    case "$f" in
      data/* | refs/audio/*)
        lk_block L1 "$f: nothing under data/ or refs/audio/ enters git (ADR-005)"
        continue
        ;;
    esac
    lower=$(printf '%s' "$f" | tr '[:upper:]' '[:lower:]')
    case "$lower" in
      *.wav | *.flac | *.mp3 | *.mp4 | *.m4a | *.aac | *.opus | *.ogg | *.webm | *.mkv | *.npy | *.npz | *.pt | *.pkl | *.parquet | *.onnx | *.sqlite)
        lk_block L1 "$f: audio, video, embeddings and model files never enter git (ADR-005)"
        ;;
    esac
  done <<EOF
$1
EOF
}

# L2 (ADR-005): no file over 1 MB. Large means data, and data stays local.
lk_rule_size() {
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    size=$(git cat-file -s ":$f" 2>/dev/null || echo 0)
    if [ "$size" -gt "$LK_MAX_BYTES" ]; then
      lk_block L2 "$f: $size bytes > 1 MB; large files are data and stay local (ADR-005)"
    fi
  done <<EOF
$1
EOF
}

# L3 (ADR-001): no cast(), no `type: ignore` anywhere; `Any` only inside src/lektyra/adapters/.
lk_rule_typing() {
  while IFS= read -r f; do
    case "$f" in
      *.py) ;;
      *) continue ;;
    esac
    added=$(lk_added_lines "$f")
    [ -z "$added" ] && continue
    if printf '%s\n' "$added" | grep -Eq '(^|[^A-Za-z0-9_])cast\('; then
      lk_block L3 "$f: cast() hides a wrong guess about the data; narrow it at the boundary (ADR-001)"
    fi
    if printf '%s\n' "$added" | grep -Eq 'type:[[:space:]]*ignore'; then
      lk_block L3 "$f: '# type: ignore' silences mypy; fix the type or wrap the library in an adapter (ADR-001)"
    fi
    case "$f" in
      src/lektyra/adapters/*) ;;
      *)
        if printf '%s\n' "$added" | grep -Eq '(import .*[^A-Za-z0-9_]Any([^A-Za-z0-9_]|$)|[:\[,][[:space:]]*Any([^A-Za-z0-9_]|$)|->[[:space:]]*Any([^A-Za-z0-9_]|$))'; then
          lk_block L3 "$f: Any is allowed only inside src/lektyra/adapters/ (ADR-001)"
        fi
        ;;
    esac
  done <<EOF
$1
EOF
}

# L4 (ADR-002): src/lektyra/domain/ does no I/O and imports nothing from adapters/ or app/.
lk_rule_domain() {
  while IFS= read -r f; do
    case "$f" in
      src/lektyra/domain/*.py) ;;
      *) continue ;;
    esac
    content=$(git show ":$f" 2>/dev/null)
    if printf '%s\n' "$content" | grep -Eq '^[[:space:]]*(from|import)[[:space:]]+lektyra\.(adapters|app|cli|settings)'; then
      lk_block L4 "$f: the domain imports nothing from adapters, app, cli or settings (ADR-002)"
    fi
    if printf '%s\n' "$content" | grep -Eq '^[[:space:]]*(from|import)[[:space:]]+(subprocess|socket|urllib|http|httpx|requests|sqlite3|psycopg|shutil|os)([[:space:].]|$)'; then
      lk_block L4 "$f: the domain does no I/O; move it to an adapter (ADR-002)"
    fi
    if printf '%s\n' "$content" | grep -Eq '(^|[^A-Za-z0-9_.])open\(|datetime\.now\(|time\.time\(|\.read_text\(|\.write_text\(|\.read_bytes\(|\.write_bytes\('; then
      lk_block L4 "$f: no files and no clock in the domain; the caller passes data and time in (ADR-002)"
    fi
  done <<EOF
$1
EOF
}

# L5 (ADR-005): no keys or tokens in what is committed. A missing scanner blocks; it never skips.
lk_rule_secrets() {
  if ! command -v gitleaks >/dev/null 2>&1; then
    lk_block L5 "gitleaks is not installed (winget install Gitleaks.Gitleaks / brew install gitleaks) (ADR-005)"
    return
  fi
  if ! gitleaks git --pre-commit --staged --redact --no-banner --log-level error >/dev/null 2>&1; then
    lk_block L5 "gitleaks found a secret in the staged changes; run: gitleaks git --pre-commit --staged --redact -v (ADR-005)"
  fi
}

# L6 (ADR-001): lint, format, strict types and the fast tests, when Python or the project changed.
lk_rule_python() {
  if ! printf '%s\n' "$1" | grep -Eq '(\.py$|^pyproject\.toml$|^uv\.lock$)'; then
    return
  fi
  if ! command -v uv >/dev/null 2>&1; then
    lk_block L6 "uv is not installed (winget install astral-sh.uv / brew install uv) (ADR-001)"
    return
  fi
  uv run --quiet ruff check . >&2 || lk_block L6 "ruff check failed (ADR-001)"
  uv run --quiet ruff format --check . >/dev/null 2>&1 || lk_block L6 "ruff format: run 'uv run ruff format .' (ADR-001)"
  uv run --quiet mypy >&2 || lk_block L6 "mypy --strict failed (ADR-001)"
  uv run --quiet pytest -q -m "not slow" >&2 || lk_block L6 "fast tests failed (ADR-001)"
}

# L9 (ADR-009): the UI's escape hatches. ESLint enforces the code style (no casts, no `!`, no `any`, no
# useEffect, no raw fetch); a disable comment or a ts-ignore would switch that off, so neither may be added.
lk_rule_web_escapes() {
  while IFS= read -r f; do
    case "$f" in
      web/node_modules/* | web/dist/*) continue ;;
      web/*.ts | web/*.tsx | web/*.js | web/*.mjs) ;;
      *) continue ;;
    esac
    added=$(lk_added_lines "$f")
    [ -z "$added" ] && continue
    if printf '%s\n' "$added" | grep -Eq 'eslint-disable|@ts-ignore|@ts-expect-error|@ts-nocheck'; then
      lk_block L9 "$f: eslint-disable / @ts-ignore switches a rule off; fix the cause (ADR-009)"
    fi
  done <<EOF
$1
EOF
}

# L9 (ADR-009): typecheck, lint and the UI's tests, when anything under web/ changed.
lk_rule_web_check() {
  if ! printf '%s\n' "$1" | grep -Eq '^web/'; then
    return
  fi
  if ! command -v npm >/dev/null 2>&1; then
    lk_block L9 "npm is not on PATH (fnm env / winget install Schniz.fnm) (ADR-009)"
    return
  fi
  if [ ! -d web/node_modules ]; then
    lk_block L9 "web/node_modules is missing: run 'npm ci' in web/ (ADR-009)"
    return
  fi
  npm --prefix web run --silent check >&2 || lk_block L9 "web: typecheck, lint or tests failed (npm run check in web/) (ADR-009)"
}

# L7: no AI attribution in a commit message.
lk_rule_attribution() {
  if grep -qiE 'co-authored-by:.*(claude|anthropic|openai|gpt|copilot)|generated with.*(claude|copilot)|noreply@anthropic\.com|🤖' "$1"; then
    lk_block L7 "AI attribution in the commit message: remove Co-Authored-By / 'Generated with' lines (AGENTS.md)"
  fi
}

# L8: a conventional subject: type(scope): what, at most 72 characters. Merges and reverts pass.
lk_rule_subject() {
  subject=$(grep -v '^#' "$1" | head -n 1)
  case "$subject" in
    Merge\ * | Revert\ *) return ;;
  esac
  if ! printf '%s' "$subject" | grep -Eq '^(feat|fix|docs|test|refactor|perf|build|ci|chore)(\([a-z0-9._-]+\))?!?: .{3,}$'; then
    lk_block L8 "subject must be 'type(scope): what' (feat, fix, docs, test, refactor, perf, build, ci, chore)"
  fi
  if [ "${#subject}" -gt 72 ]; then
    lk_block L8 "subject is ${#subject} characters; at most 72"
  fi
}
