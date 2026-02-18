#!/usr/bin/env bash
# post-tool-use-edits.sh — PostToolUse:Write|Edit hook (async)
# Logs file edits as session observations.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

TOOL_NAME=$(field "tool_name")
FILE_PATH=$(field "tool_input.file_path")

[ -z "$FILE_PATH" ] && exit 0

observe_event "file_edit" "Edited: ${FILE_PATH}" \
  "{\"tool\": \"${TOOL_NAME}\", \"file_path\": \"${FILE_PATH}\"}"

exit 0
