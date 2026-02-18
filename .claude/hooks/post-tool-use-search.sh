#!/usr/bin/env bash
# post-tool-use-search.sh — PostToolUse:Grep|Glob|WebSearch|WebFetch hook (async)
# Logs search/research activity as session observations.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

TOOL_NAME=$(field "tool_name")

# Extract the relevant query depending on tool
case "$TOOL_NAME" in
  Grep)      QUERY=$(field "tool_input.pattern") ;;
  Glob)      QUERY=$(field "tool_input.pattern") ;;
  WebSearch) QUERY=$(field "tool_input.query") ;;
  WebFetch)  QUERY=$(field "tool_input.url") ;;
  *)         QUERY="unknown" ;;
esac

[ -z "$QUERY" ] && exit 0

# Truncate query to 200 chars
QUERY="${QUERY:0:200}"

observe_event "research" "Search: ${TOOL_NAME} — ${QUERY}" \
  "{\"tool\": \"${TOOL_NAME}\", \"query\": \"${QUERY}\"}"

exit 0
