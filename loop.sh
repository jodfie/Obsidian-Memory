#!/usr/bin/env bash
#
# Ralph Wiggum Development Loop
# Usage:
#   ./loop.sh              # Build mode, unlimited
#   ./loop.sh 20           # Build mode, max 20 iterations
#   ./loop.sh plan         # Plan mode, unlimited
#   ./loop.sh plan 5       # Plan mode, 5 iterations
#

set -euo pipefail

MODE="build"
MAX_ITERATIONS=0
ITERATION=0

# Parse arguments
if [[ "${1:-}" == "plan" ]]; then
  MODE="plan"
  shift
fi

if [[ "${1:-}" =~ ^[0-9]+$ ]]; then
  MAX_ITERATIONS=$1
fi

PROMPT_FILE="PROMPT_${MODE}.md"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Error: $PROMPT_FILE not found"
  exit 1
fi

echo "Starting Ralph Wiggum loop in $MODE mode..."
echo "Max iterations: ${MAX_ITERATIONS:-unlimited}"
echo ""

while true; do
  ((ITERATION++))

  if [[ $MAX_ITERATIONS -gt 0 && $ITERATION -gt $MAX_ITERATIONS ]]; then
    echo "Reached max iterations ($MAX_ITERATIONS)"
    break
  fi

  echo "=== Iteration $ITERATION ==="

  # Run Claude with the prompt
  if ! claude -p --dangerously-skip-permissions --model opus < "$PROMPT_FILE"; then
    echo "Claude exited with error, continuing..."
  fi

  # Small delay between iterations
  sleep 2
done

echo "Loop complete after $ITERATION iterations"
