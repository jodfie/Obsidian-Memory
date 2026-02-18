#!/usr/bin/env bash
# subagent-start.sh — SubagentStart hook (async)
# Logs subagent spawns as session observations.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

AGENT_TYPE=$(field "agent_type")
AGENT_ID=$(field "agent_id")

[ -z "$AGENT_TYPE" ] && exit 0

observe_event "tool_use" "Subagent spawned: ${AGENT_TYPE}" \
  "{\"agent_type\": \"${AGENT_TYPE}\", \"agent_id\": \"${AGENT_ID}\"}"

exit 0
