# Hooks Rewrite Design — Comprehensive Async Hooks for Obsidian-Memory

**Date:** 2026-02-18
**Status:** Implemented
**Goal:** Maximize hook-based automation, minimize MCP tool calls for token efficiency

## Overview

Rewrite all 5 broken hooks (wrong API format) and add 5 new hooks. Use async for all logging hooks (non-blocking), sync for decision-making hooks. Move scripts from `hooks/` to `.claude/hooks/` (standard Claude Code location).

10 hooks total replace what would otherwise require manual MCP `session_observe` calls, saving ~200-500 tokens per observation.

## File Structure

```
.claude/hooks/
├── _lib.sh                    # Shared functions (API calls, env reading, JSON parsing)
├── session-start.sh           # SessionStart:startup — sync
├── user-prompt-submit.sh      # UserPromptSubmit — async
├── pre-tool-use-bash.sh       # PreToolUse:Bash — sync (merges validate-bash.sh)
├── post-tool-use-edits.sh     # PostToolUse:Write|Edit — async
├── post-tool-use-search.sh    # PostToolUse:Grep|Glob|WebSearch|WebFetch — async
├── post-tool-failure.sh       # PostToolUseFailure — async
├── subagent-start.sh          # SubagentStart — async
├── pre-compact.sh             # PreCompact — sync
├── stop.sh                    # Stop — sync
└── session-end.sh             # SessionEnd — async
```

Removed:
- `hooks/` directory (old broken format)
- `.claude/scripts/validate-bash.sh` (merged into pre-tool-use-bash.sh)
- `.claude/scripts/statusline.sh` kept as-is (unrelated)

## Hook Configuration

Added to `.claude/settings.local.json` under `hooks` key:

| Hook | Event | Matcher | Async | Timeout |
|------|-------|---------|-------|---------|
| session-start.sh | SessionStart | `startup` | no | 10s |
| user-prompt-submit.sh | UserPromptSubmit | — | yes | 5s |
| pre-tool-use-bash.sh | PreToolUse | `Bash` | no | 5s |
| post-tool-use-edits.sh | PostToolUse | `Write\|Edit` | yes | 5s |
| post-tool-use-search.sh | PostToolUse | `Grep\|Glob\|WebSearch\|WebFetch` | yes | 5s |
| post-tool-failure.sh | PostToolUseFailure | — | yes | 5s |
| subagent-start.sh | SubagentStart | — | yes | 5s |
| pre-compact.sh | PreCompact | — | no | 30s |
| stop.sh | Stop | — | no | 10s |
| session-end.sh | SessionEnd | — | yes | 30s |

## Shared Library (_lib.sh)

Provides:
- `API_URL` — defaults to `http://localhost:8765`
- `SESSION_ID` — from `OBSIDIAN_MEMORY_SESSION_ID` env var (set by session-start.sh via CLAUDE_ENV_FILE)
- `read_input()` — reads stdin JSON, tolerates parse failures
- `api_post(endpoint, data)` — curl POST with timeout and error handling
- `api_get(endpoint)` — curl GET
- `observe_event(event_type, content, metadata_json)` — POST /api/sessions/observe
- `is_backend_up()` — health check with short timeout
- `require_session()` — check SESSION_ID is set, exit 0 if not

## Hook Behaviors

### session-start.sh (sync)
1. Health check backend
2. POST /api/sessions with `{ session_id, project }`
3. Write `OBSIDIAN_MEMORY_SESSION_ID`, `OBSIDIAN_MEMORY_API_URL`, `OBSIDIAN_MEMORY_PROJECT` to `$CLAUDE_ENV_FILE`
4. Return `additionalContext` with project context

### user-prompt-submit.sh (async)
1. Skip if no SESSION_ID
2. Truncate prompt to 500 chars
3. observe_event "user_prompt" with prompt preview and length metadata

### pre-tool-use-bash.sh (sync)
1. Extract command from tool_input
2. Check forbidden patterns (.env, .git/, node_modules, etc.)
3. Exit 2 to block, exit 0 to allow

### post-tool-use-edits.sh (async)
1. Extract file_path from tool_input
2. observe_event "file_edit" with file path and tool name

### post-tool-use-search.sh (async)
1. Extract query/pattern/url depending on tool
2. observe_event "research" with search details

### post-tool-failure.sh (async)
1. Skip if is_interrupt is true
2. observe_event "error" with tool name, error message, input summary

### subagent-start.sh (async)
1. observe_event "tool_use" with agent_type and agent_id

### pre-compact.sh (sync)
1. POST /api/sessions/{id}/summary with force_incremental: true
2. Log summary status to stderr

### stop.sh (sync)
1. If stop_hook_active is true: exit 0 immediately (prevent loops)
2. Check session event count via GET /api/sessions/{id}
3. If >5 events and no summary: trigger summary
4. Exit 0 (never blocks stop)

### session-end.sh (async)
1. POST /api/sessions/{id}/end with auto_summarize: true

## Error Handling

- **Backend down:** session-start.sh exits 0 silently, no env vars set, all subsequent hooks become no-ops
- **JSON parse failures:** jq uses `// empty` fallback, INPUT defaults to `{}`
- **Rate limiting (429):** async hooks ignore; sync hooks log warning, exit 0
- **Timeouts:** all hooks fail-open (command proceeds, compaction proceeds, stop proceeds)
- **CLAUDE_ENV_FILE not set:** falls back to shell env OBSIDIAN_MEMORY_SESSION_ID if manually set

## Session Event Types

Maps to backend SessionEventType enum:
- `user_prompt` — user submitted a prompt
- `file_edit` — file was written or edited
- `research` — search/grep/web lookup performed
- `error` — tool execution failed
- `tool_use` — subagent spawned
- `command` — bash command executed (if we add PostToolUse:Bash later)

## What This Replaces

Previously required explicit MCP calls:
- `session_observe` for every event → now automatic via hooks
- `session_summary` before compaction → now automatic via PreCompact hook
- `session_context` at start → now automatic via SessionStart hook

The only MCP tools still needed for manual use:
- `mem_read`, `mem_write`, `mem_search` — note operations
- `build_context`, `graph_traverse`, `graph_similar` — knowledge graph
- `recall`, `get_profile` — memory retrieval
- `project_list`, `project_switch` — project management
