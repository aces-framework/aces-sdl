#!/usr/bin/env bash
set -euo pipefail

FILE_PATH=$(jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
implementations/python/.venv/bin/python tools/check_repo_policy.py --check-set file-local "$FILE_PATH"
