#!/usr/bin/env bash
# Fails (exit 1) if any banned pattern appears in tracked files, built output or commit messages.
# Usage: scripts/check_branding.sh [paths...]
set -u
cd "$(git rev-parse --show-toplevel)"
SELF="scripts/check_branding.sh"

# Patterns are never stored in this repo. Sources, in order:
#   1. BRANDING_PATTERNS       newline-separated regexes (the CI secret)
#   2. BRANDING_PATTERNS_FILE  path to a file of regexes
#   3. ../nyc-bike-lane-priority-reference/branding_terms.txt (local development; skipped when
#      BRANDING_NO_LOCAL_FALLBACK=1)
# Blank lines and lines starting with # are ignored. With no source: exit 2 (fail closed).
LOCAL_TERMS="../nyc-bike-lane-priority-reference/branding_terms.txt"
RAW=""
if [ -n "${BRANDING_PATTERNS:-}" ]; then
  RAW=$BRANDING_PATTERNS
elif [ -n "${BRANDING_PATTERNS_FILE:-}" ]; then
  [ -r "$BRANDING_PATTERNS_FILE" ] || { echo "check_branding: BRANDING_PATTERNS_FILE is not readable" >&2; exit 2; }
  RAW=$(cat "$BRANDING_PATTERNS_FILE")
elif [ "${BRANDING_NO_LOCAL_FALLBACK:-}" != "1" ] && [ -r "$LOCAL_TERMS" ]; then
  RAW=$(cat "$LOCAL_TERMS")
fi
PATTERNS=$(printf '%s\n' "$RAW" | tr -d '\r' | grep -vE '^[[:space:]]*(#|$)') || true
if [ -z "$PATTERNS" ]; then
  echo "check_branding: branding patterns not configured (set BRANDING_PATTERNS or BRANDING_PATTERNS_FILE)" >&2
  exit 2
fi

# \b: grep -E handles it on BSD and GNU grep; git grep needs -P (-E ignores \b on macOS).
PFILE=$(mktemp)
ERRF=$(mktemp)
trap 'rm -f "$PFILE" "$ERRF"' EXIT
printf '%s\n' "$PATTERNS" > "$PFILE"

status=0
SELF_ABS="$(cd "$(dirname "$SELF")" && pwd -P)/$(basename "$SELF")"

# Lockfile integrity hashes are random base64 and can contain a banned term by chance.
LOCK_FILTER='package-lock\.json:[0-9]+:.*"integrity":'

# scan LABEL CMD...: run a grep-like command; 0 = hit, 1 = clean, >=2 = error (fail closed).
scan() {
  label=$1; shift
  rc=0
  out=$("$@" 2>"$ERRF") || rc=$?
  if [ "$rc" -ge 2 ]; then
    echo "check_branding: scan of $label failed (exit $rc)" >&2; cat "$ERRF" >&2; exit 2
  fi
  if [ "$rc" -eq 0 ]; then
    out=$(printf '%s\n' "$out" | grep -vE "$LOCK_FILTER") || true
    if [ -n "$out" ]; then echo "BRANDING HIT in $label"; echo "$out"; status=1; fi
  fi
}

if [ "$#" -gt 0 ]; then
  for f in "$@"; do
    [ -e "$f" ] || { echo "check_branding: no such path: $f" >&2; exit 2; }
  done
  files=()
  while IFS= read -r -d '' f; do
    abs="$(cd "$(dirname "$f")" && pwd -P)/$(basename "$f")"
    [ "$abs" = "$SELF_ABS" ] || files+=("$f")
  done < <(find "$@" -type f -print0)
  [ "${#files[@]}" -gt 0 ] && scan "paths" grep -niIHE -f "$PFILE" -- "${files[@]}"
else
  scan "tracked files" git grep -niIP -f "$PFILE" -- . ":(exclude)$SELF"
  if [ -d site/dist ]; then
    scan "site/dist" grep -rniIE -f "$PFILE" site/dist
  fi
  if git rev-parse -q --verify HEAD >/dev/null 2>&1; then
    LOGF=$(mktemp)
    git log --format=%B >"$LOGF" 2>"$ERRF" || { echo "check_branding: git log failed" >&2; cat "$ERRF" >&2; rm -f "$LOGF"; exit 2; }
    scan "commit messages" grep -niIE -f "$PFILE" "$LOGF"
    rm -f "$LOGF"
  fi
fi
exit $status
