# Hooks Rewrite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite 5 broken hooks + add 5 new hooks for automatic Obsidian-Memory session tracking, replacing manual MCP tool calls.

**Architecture:** Shell scripts in `.claude/hooks/` using JSON stdin (Claude Code hooks API). Shared `_lib.sh` library for API calls. Async hooks for logging, sync hooks for decisions. Environment variable propagation via `$CLAUDE_ENV_FILE`.

**Tech Stack:** Bash, jq, curl. Backend API at `http://localhost:8765`.

---

### Task 1: Create shared library `_lib.sh`

**Files:**
- Create: `.claude/hooks/_lib.sh`

**Step 1: Write the shared library**

```bash
#!/usr/bin/env bash
# _lib.sh — Shared functions for Obsidian-Memory Claude Code hooks
# Source this file at the top of each hook: source "$(dirname "$0")/_lib.sh"

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8765}"
SESSION_ID="${OBSIDIAN_MEMORY_SESSION_ID:-}"

# ── Input parsing ───────────────────────────────────────────────────
INPUT=""
read_input() {
  INPUT=$(cat 2>/dev/null || echo '{}')
  # Validate it's JSON; if not, reset to empty object
  if ! echo "$INPUT" | jq empty 2>/dev/null; then
    INPUT='{}'
  fi
}

# Extract a field from INPUT. Returns empty string on missing/null.
field() {
  echo "$INPUT" | jq -r ".$1 // empty" 2>/dev/null || echo ""
}

# ── Session guard ───────────────────────────────────────────────────
require_session() {
  if [ -z "$SESSION_ID" ]; then
    exit 0
  fi
}

# ── API helpers ─────────────────────────────────────────────────────
api_get() {
  curl -sf --connect-timeout 2 --max-time 5 \
    -H "Content-Type: application/json" \
    "${API_URL}/$1" 2>/dev/null || echo ""
}

api_post() {
  local endpoint="$1"
  local data="$2"
  curl -sf --connect-timeout 2 --max-time 5 \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$data" \
    "${API_URL}/${endpoint}" 2>/dev/null || echo ""
}

is_backend_up() {
  curl -sf --connect-timeout 2 --max-time 3 \
    "${API_URL}/health" >/dev/null 2>&1
}

# ── Observe helper ──────────────────────────────────────────────────
# Usage: observe_event "event_type" "content" '{"key": "value"}'
observe_event() {
  local event_type="$1"
  local content="$2"
  local metadata="${3:-{\}}"

  # Escape content for JSON (handle quotes and newlines)
  local escaped_content
  escaped_content=$(echo "$content" | jq -Rs '.' 2>/dev/null || echo "\"$content\"")

  api_post "api/sessions/observe" "{
    \"session_id\": \"${SESSION_ID}\",
    \"event_type\": \"${event_type}\",
    \"content\": ${escaped_content},
    \"metadata\": ${metadata}
  }" >/dev/null 2>&1 || true
}
```

**Step 2: Verify the file is syntactically valid**

Run: `bash -n .claude/hooks/_lib.sh`
Expected: No output (clean parse)

**Step 3: Commit**

```bash
git add .claude/hooks/_lib.sh
git commit -m "feat(hooks): add shared library for Obsidian-Memory hooks"
```

---

### Task 2: Create `session-start.sh`

**Files:**
- Create: `.claude/hooks/session-start.sh`

**Step 1: Write the hook**

```bash
#!/usr/bin/env bash
# session-start.sh — SessionStart hook (sync, matcher: startup)
# Creates a new Obsidian-Memory session and persists env vars via CLAUDE_ENV_FILE.

source "$(dirname "$0")/_lib.sh"
read_input

# Extract fields from SessionStart input
CLAUDE_SESSION_ID=$(field "session_id")
SOURCE=$(field "source")
MODEL=$(field "model")
CWD=$(field "cwd")

# Derive project name from cwd (last directory component)
PROJECT=$(basename "$CWD" 2>/dev/null || echo "")

# Check if backend is available
if ! is_backend_up; then
  exit 0
fi

# Create session
RESPONSE=$(api_post "api/sessions" "{
  \"session_id\": \"${CLAUDE_SESSION_ID}\",
  \"project\": \"${PROJECT}\"
}")

# Extract session_id from response (backend may assign a different one)
BACKEND_SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id // empty' 2>/dev/null || echo "")
if [ -z "$BACKEND_SESSION_ID" ]; then
  BACKEND_SESSION_ID="$CLAUDE_SESSION_ID"
fi

# Persist env vars for all subsequent hooks and Bash commands
if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo "export OBSIDIAN_MEMORY_SESSION_ID=\"${BACKEND_SESSION_ID}\"" >> "$CLAUDE_ENV_FILE"
  echo "export OBSIDIAN_MEMORY_API_URL=\"${API_URL}\"" >> "$CLAUDE_ENV_FILE"
  echo "export OBSIDIAN_MEMORY_PROJECT=\"${PROJECT}\"" >> "$CLAUDE_ENV_FILE"
fi

# Log the session start as first observation
SESSION_ID="$BACKEND_SESSION_ID"
observe_event "observation" "Session started: model=${MODEL}, source=${SOURCE}, project=${PROJECT}" \
  "{\"model\": \"${MODEL}\", \"source\": \"${SOURCE}\", \"project\": \"${PROJECT}\"}"

# Return context for Claude
jq -n --arg ctx "Obsidian-Memory session active: ${BACKEND_SESSION_ID} (project: ${PROJECT})" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'

exit 0
```

**Step 2: Make executable and verify syntax**

Run: `chmod +x .claude/hooks/session-start.sh && bash -n .claude/hooks/session-start.sh`
Expected: No output (clean parse)

**Step 3: Commit**

```bash
git add .claude/hooks/session-start.sh
git commit -m "feat(hooks): add session-start hook with env propagation"
```

---

### Task 3: Create `user-prompt-submit.sh`

**Files:**
- Create: `.claude/hooks/user-prompt-submit.sh`

**Step 1: Write the hook**

```bash
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
```

**Step 2: Make executable and verify syntax**

Run: `chmod +x .claude/hooks/user-prompt-submit.sh && bash -n .claude/hooks/user-prompt-submit.sh`
Expected: No output

**Step 3: Commit**

```bash
git add .claude/hooks/user-prompt-submit.sh
git commit -m "feat(hooks): add user-prompt-submit hook (async)"
```

---

### Task 4: Create `pre-tool-use-bash.sh` (merge validate-bash.sh)

**Files:**
- Create: `.claude/hooks/pre-tool-use-bash.sh`
- Delete: `.claude/scripts/validate-bash.sh` (after verifying merge)

**Step 1: Write the hook**

```bash
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
```

**Step 2: Make executable and verify syntax**

Run: `chmod +x .claude/hooks/pre-tool-use-bash.sh && bash -n .claude/hooks/pre-tool-use-bash.sh`
Expected: No output

**Step 3: Verify it blocks correctly**

Run: `echo '{"tool_input":{"command":"cat .env"}}' | bash .claude/hooks/pre-tool-use-bash.sh; echo "Exit: $?"`
Expected: `ERROR: Access to '\.env' is blocked by security policy` on stderr, `Exit: 2`

**Step 4: Verify it allows clean commands**

Run: `echo '{"tool_input":{"command":"ls -la"}}' | bash .claude/hooks/pre-tool-use-bash.sh; echo "Exit: $?"`
Expected: `Exit: 0`

**Step 5: Commit**

```bash
git add .claude/hooks/pre-tool-use-bash.sh
git commit -m "feat(hooks): add pre-tool-use-bash hook (merged from validate-bash.sh)"
```

---

### Task 5: Create `post-tool-use-edits.sh`

**Files:**
- Create: `.claude/hooks/post-tool-use-edits.sh`

**Step 1: Write the hook**

```bash
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
```

**Step 2: Make executable and verify syntax**

Run: `chmod +x .claude/hooks/post-tool-use-edits.sh && bash -n .claude/hooks/post-tool-use-edits.sh`
Expected: No output

**Step 3: Commit**

```bash
git add .claude/hooks/post-tool-use-edits.sh
git commit -m "feat(hooks): add post-tool-use-edits hook (async)"
```

---

### Task 6: Create `post-tool-use-search.sh`

**Files:**
- Create: `.claude/hooks/post-tool-use-search.sh`

**Step 1: Write the hook**

```bash
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
```

**Step 2: Make executable and verify syntax**

Run: `chmod +x .claude/hooks/post-tool-use-search.sh && bash -n .claude/hooks/post-tool-use-search.sh`
Expected: No output

**Step 3: Commit**

```bash
git add .claude/hooks/post-tool-use-search.sh
git commit -m "feat(hooks): add post-tool-use-search hook (async)"
```

---

### Task 7: Create `post-tool-failure.sh`

**Files:**
- Create: `.claude/hooks/post-tool-failure.sh`

**Step 1: Write the hook**

```bash
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
```

**Step 2: Make executable and verify syntax**

Run: `chmod +x .claude/hooks/post-tool-failure.sh && bash -n .claude/hooks/post-tool-failure.sh`
Expected: No output

**Step 3: Commit**

```bash
git add .claude/hooks/post-tool-failure.sh
git commit -m "feat(hooks): add post-tool-failure hook (async)"
```

---

### Task 8: Create `subagent-start.sh`

**Files:**
- Create: `.claude/hooks/subagent-start.sh`

**Step 1: Write the hook**

```bash
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
```

**Step 2: Make executable and verify syntax**

Run: `chmod +x .claude/hooks/subagent-start.sh && bash -n .claude/hooks/subagent-start.sh`
Expected: No output

**Step 3: Commit**

```bash
git add .claude/hooks/subagent-start.sh
git commit -m "feat(hooks): add subagent-start hook (async)"
```

---

### Task 9: Create `pre-compact.sh`

**Files:**
- Create: `.claude/hooks/pre-compact.sh`

**Step 1: Write the hook**

```bash
#!/usr/bin/env bash
# pre-compact.sh — PreCompact hook (sync)
# Triggers session summarization before context is lost to compaction.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

if ! is_backend_up; then
  exit 0
fi

TRIGGER=$(field "trigger")

echo "[obsidian-memory] PreCompact (${TRIGGER}): Triggering session summarization..." >&2

# Trigger incremental summary with longer timeout
RESPONSE=$(curl -sf --connect-timeout 5 --max-time 25 \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"force_incremental": true}' \
  "${API_URL}/api/sessions/${SESSION_ID}/summary" 2>/dev/null || echo "")

if echo "$RESPONSE" | jq -e '.key_learnings' >/dev/null 2>&1; then
  echo "[obsidian-memory] Session summarized successfully before compaction" >&2
else
  echo "[obsidian-memory] WARNING: Summarization may have failed or AI unavailable" >&2
fi

exit 0
```

**Step 2: Make executable and verify syntax**

Run: `chmod +x .claude/hooks/pre-compact.sh && bash -n .claude/hooks/pre-compact.sh`
Expected: No output

**Step 3: Commit**

```bash
git add .claude/hooks/pre-compact.sh
git commit -m "feat(hooks): add pre-compact hook for session summarization"
```

---

### Task 10: Create `stop.sh`

**Files:**
- Create: `.claude/hooks/stop.sh`

**Step 1: Write the hook**

```bash
#!/usr/bin/env bash
# stop.sh — Stop hook (sync)
# Ensures session has a summary before Claude stops. Never blocks stop.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

# Prevent infinite loops — if stop hook already active, exit immediately
STOP_HOOK_ACTIVE=$(field "stop_hook_active")
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

if ! is_backend_up; then
  exit 0
fi

# Check current session state
SESSION_INFO=$(api_get "api/sessions/${SESSION_ID}")
if [ -z "$SESSION_INFO" ]; then
  exit 0
fi

EVENT_COUNT=$(echo "$SESSION_INFO" | jq -r '.event_count // 0' 2>/dev/null || echo "0")

# If session has enough events, trigger a summary (fire-and-forget)
if [ "$EVENT_COUNT" -gt 5 ]; then
  api_post "api/sessions/${SESSION_ID}/summary" '{}' >/dev/null 2>&1 || true
fi

exit 0
```

**Step 2: Make executable and verify syntax**

Run: `chmod +x .claude/hooks/stop.sh && bash -n .claude/hooks/stop.sh`
Expected: No output

**Step 3: Commit**

```bash
git add .claude/hooks/stop.sh
git commit -m "feat(hooks): add stop hook for session summary trigger"
```

---

### Task 11: Create `session-end.sh`

**Files:**
- Create: `.claude/hooks/session-end.sh`

**Step 1: Write the hook**

```bash
#!/usr/bin/env bash
# session-end.sh — SessionEnd hook (async)
# Ends the Obsidian-Memory session with auto-summarization.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

REASON=$(field "reason")

# End the session (backend will auto-summarize if threshold met)
api_post "api/sessions/${SESSION_ID}/end" "{\"auto_summarize\": true}" >/dev/null 2>&1 || true

exit 0
```

**Step 2: Make executable and verify syntax**

Run: `chmod +x .claude/hooks/session-end.sh && bash -n .claude/hooks/session-end.sh`
Expected: No output

**Step 3: Commit**

```bash
git add .claude/hooks/session-end.sh
git commit -m "feat(hooks): add session-end hook (async)"
```

---

### Task 12: Wire hooks into settings and clean up old files

**Files:**
- Modify: `.claude/settings.local.json` — add `hooks` key
- Delete: `.claude/scripts/validate-bash.sh` — merged into pre-tool-use-bash.sh
- Delete: `hooks/` directory — old broken format

**Step 1: Add hooks configuration to `.claude/settings.local.json`**

Add the `hooks` key at the top level of the JSON object (alongside existing `permissions` and `enableAllProjectMcpServers`). The full hooks config is:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-start.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/user-prompt-submit.sh",
            "async": true,
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/pre-tool-use-bash.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-tool-use-edits.sh",
            "async": true,
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Grep|Glob|WebSearch|WebFetch",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-tool-use-search.sh",
            "async": true,
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUseFailure": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-tool-failure.sh",
            "async": true,
            "timeout": 5
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/subagent-start.sh",
            "async": true,
            "timeout": 5
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/pre-compact.sh",
            "timeout": 30
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/stop.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-end.sh",
            "async": true,
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Step 2: Remove the old PreToolUse hook reference if present**

Check if `.claude/settings.local.json` has an existing hooks entry pointing to `validate-bash.sh` and remove it — the new `pre-tool-use-bash.sh` replaces it.

**Step 3: Delete old files**

```bash
rm .claude/scripts/validate-bash.sh
rm -rf hooks/
```

**Step 4: Commit**

```bash
git add .claude/settings.local.json
git rm .claude/scripts/validate-bash.sh
git rm -r hooks/
git commit -m "feat(hooks): wire 10 hooks into settings, remove old hooks directory"
```

---

### Task 13: Verify all hooks parse and are executable

**Step 1: Check all scripts have executable bit and valid syntax**

Run: `for f in .claude/hooks/*.sh; do echo "=== $f ==="; bash -n "$f" && echo "OK" || echo "FAIL"; done`
Expected: All show OK

**Step 2: Dry-run the bash validator**

Run: `echo '{"tool_input":{"command":"rm -rf /"}}' | bash .claude/hooks/pre-tool-use-bash.sh 2>&1; echo "Exit: $?"`
Expected: Blocked with exit 2

Run: `echo '{"tool_input":{"command":"echo hello"}}' | bash .claude/hooks/pre-tool-use-bash.sh 2>&1; echo "Exit: $?"`
Expected: Exit: 0

**Step 3: Dry-run session-start without backend**

Run: `echo '{"session_id":"test","source":"startup","model":"test","cwd":"/tmp"}' | bash .claude/hooks/session-start.sh 2>&1; echo "Exit: $?"`
Expected: Exit: 0 (graceful degradation, no backend = silent exit)

**Step 4: Final commit (if any fixes needed)**

```bash
git add -A .claude/hooks/
git commit -m "fix(hooks): address any issues found during verification"
```

---

### Task 14: Update design doc with implementation status

**Files:**
- Modify: `docs/plans/2026-02-18-hooks-rewrite-design.md`

**Step 1: Update status to "Implemented"**

Change `**Status:** Approved` to `**Status:** Implemented`

**Step 2: Commit**

```bash
git add docs/plans/2026-02-18-hooks-rewrite-design.md
git commit -m "docs: mark hooks rewrite design as implemented"
```
