#!/usr/bin/env bash
# pre-tool-use-bash.sh — PreToolUse:Bash hook (sync)
# Validates bash commands against forbidden patterns. Blocks dangerous commands.
# Merges functionality from the old .claude/scripts/validate-bash.sh

source "$(dirname "$0")/_lib.sh"
read_input

COMMAND=$(field "tool_input.command")

# If no command found, allow it
if [ -z "$COMMAND" ]; then
  exit 0
fi

# Define forbidden patterns
FORBIDDEN_PATTERNS=(
  "\.env"
  "\.ansible/"
  "\.terraform/"
  "build/"
  "dist/"
  "node_modules"
  "__pycache__"
  "\.git/"
  "venv/"
  "\.pyc$"
  "\.csv$"
  "\.log$"
)

# Check if command contains any forbidden patterns
for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    echo "ERROR: Access to '$pattern' is blocked by security policy" >&2
    exit 2
  fi
done

# Command is clean, allow it
exit 0
