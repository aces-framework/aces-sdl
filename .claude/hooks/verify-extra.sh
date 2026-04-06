#!/usr/bin/env bash
# Project-specific implementation checks.
# Sourced by the user-level verify-implementation.sh Stop hook.
# $CHANGED is passed in as an env var containing the git diff file list.
# Output any failure reasons to stdout; empty output = all checks pass.

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$ROOT/implementations/python/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo -n "Missing implementations/python/.venv/bin/python; cannot run repo verification."
  exit 0
fi

if ! "$PY" "$ROOT/tools/check_repo_policy.py" >/tmp/aces-sdl-policy.out 2>&1; then
  tr '\n' ' ' </tmp/aces-sdl-policy.out
  exit 0
fi

if ! "$PY" "$ROOT/tools/check_requirement_governance.py" >/tmp/aces-sdl-gc.out 2>&1; then
  tr '\n' ' ' </tmp/aces-sdl-gc.out
  exit 0
fi

echo -n ""
