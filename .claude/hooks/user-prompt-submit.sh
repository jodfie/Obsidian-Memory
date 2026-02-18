#!/usr/bin/env bash
# user-prompt-submit.sh — UserPromptSubmit hook (async)
# Logs user prompts as session observations.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

PROMPT=$(field "prompt")
[ -z "$PROMPT" ] && exit 0

# Truncate to 500 chars
PROMPT_PREVIEW="${PROMPT:0:500}"
PROMPT_LENGTH=${#PROMPT}

observe_event "user_prompt" "User prompt: ${PROMPT_PREVIEW}" \
  "{\"prompt_length\": ${PROMPT_LENGTH}}"

exit 0
