#!/usr/bin/env bash
# Project-specific implementation checks.
# Sourced by the user-level verify-implementation.sh Stop hook.
# $CHANGED is passed in as an env var containing the git diff file list.
# Output any failure reasons to stdout; empty output = all checks pass.

REASONS=""

# Example checks:
# Check: If controllers changed, docs/API.md should be updated
# HAS_CONTROLLER=$(echo "$CHANGED" | grep -c 'Controller\.java' || true)
# HAS_API_DOC=$(echo "$CHANGED" | grep -c 'docs/API.md' || true)
# if [ "$HAS_CONTROLLER" -gt 0 ] && [ "$HAS_API_DOC" -eq 0 ]; then
#  REASONS="${REASONS}New controller added but docs/API.md not updated. "
# fi

# Check: If controllers changed, MCP tools (lib.js/index.js) should be updated
# HAS_LIB=$(echo "$CHANGED" | grep -c 'lib\.js' || true)
# HAS_INDEX=$(echo "$CHANGED" | grep -c 'index\.js' || true)
# if [ "$HAS_CONTROLLER" -gt 0 ] && { [ "$HAS_LIB" -eq 0 ] || [ "$HAS_INDEX" -eq 0 ]; }; then
#  REASONS="${REASONS}New controller added but MCP tools not updated (lib.js/index.js). "
# fi
#

echo -n "$REASONS"
