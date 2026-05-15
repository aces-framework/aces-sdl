#!/bin/bash
# Block edits to sensitive files and generated authority surfaces.
FILE_PATH=$(jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

BASENAME=$(basename "$FILE_PATH")

# Block .env files
if [[ "$BASENAME" == .env* ]] || [[ "$BASENAME" == "local_settings.py" ]]; then
    echo "BLOCKED: Editing $BASENAME is not allowed. These files contain secrets." >&2
    exit 2
fi

# Block key/credential files
if [[ "$BASENAME" == *.key ]] || [[ "$BASENAME" == *.pem ]] || [[ "$BASENAME" == "credentials"* ]]; then
    echo "BLOCKED: Editing $BASENAME is not allowed. These files contain secrets." >&2
    exit 2
fi

# Block direct edits to generated schemas.
if [[ "$FILE_PATH" == contracts/schemas/* ]]; then
    echo "BLOCKED: contracts/schemas/ is generated. Update generator inputs and regenerate instead." >&2
    exit 2
fi

exit 0
