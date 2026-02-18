#!/usr/bin/env bash
# post-tool-failure.sh — PostToolUseFailure hook (async)
# Logs tool failures as session error observations.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

# Skip user interrupts — not real failures
IS_INTERRUPT=$(field "is_interrupt")
[ "$IS_INTERRUPT" = "true" ] && exit 0

TOOL_NAME=$(field "tool_name")
ERROR=$(field "error")

[ -z "$ERROR" ] && exit 0

# Truncate error to 300 chars
ERROR="${ERROR:0:300}"

observe_event "error" "Tool failed: ${TOOL_NAME} — ${ERROR}" \
  "{\"tool\": \"${TOOL_NAME}\", \"error\": \"${ERROR}\"}"

exit 0
