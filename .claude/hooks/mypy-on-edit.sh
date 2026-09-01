#!/usr/bin/env bash
# PostToolUse hook: type-check a src/gramps_mcp file right after it's edited,
# instead of waiting for CI to catch it.
set -euo pipefail

INPUT="${TOOL_INPUT:-$(cat)}"
FILE=$(echo "$INPUT" | jq -r '.file_path // .filePath // empty' 2>/dev/null || echo "")

[[ -z "$FILE" ]] && exit 0
[[ "$FILE" != *.py ]] && exit 0
[[ "$FILE" != *"/src/gramps_mcp/"* ]] && exit 0
[[ ! -f "$FILE" ]] && exit 0

cd "$(dirname "$0")/../.." || exit 0
uv run mypy "$FILE" --ignore-missing-imports 2>&1 | head -20
exit 0
