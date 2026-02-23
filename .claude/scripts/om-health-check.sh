#!/usr/bin/env bash
# om-health-check.sh — Comprehensive Obsidian-Memory health diagnostics
# Tests all components: API, MCP, hooks, remote sync
#
# Usage: ./om-health-check.sh [--fix] [--verbose]

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

FIX_MODE=false
VERBOSE=false
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8765}"
REMOTE_URL="${OBSIDIAN_MEMORY_REMOTE_URL:-http://memory.redleif.dev}"
SESSION_FILE="/tmp/obsidian-memory-session.json"

# Parse arguments
for arg in "$@"; do
  case $arg in
    --fix) FIX_MODE=true ;;
    --verbose) VERBOSE=true ;;
  esac
done

# ── Helpers ─────────────────────────────────────────────────────────
log_test() { echo -e "${BLUE}[TEST]${NC} $1"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_info() { [ "$VERBOSE" = true ] && echo -e "${BLUE}[INFO]${NC} $1" || true; }
log_fix() { echo -e "${GREEN}[FIX]${NC} $1"; }

# ── Test Functions ──────────────────────────────────────────────────

test_local_api() {
  log_test "Testing local API at ${API_URL}"

  if ! response=$(curl -sf --connect-timeout 3 "${API_URL}/health" 2>/dev/null); then
    log_fail "Local API not responding at ${API_URL}"
    log_info "Check if API server is running: systemctl status obsidian-memory"
    return 1
  fi

  local status=$(echo "$response" | jq -r '.status' 2>/dev/null || echo "")
  if [ "$status" = "healthy" ]; then
    local notes=$(echo "$response" | jq -r '.notes.total // 0' 2>/dev/null || echo "0")
    local projects=$(echo "$response" | jq -r '.projects.total // 0' 2>/dev/null || echo "0")
    # Handle "null" string from jq
    [ "$notes" = "null" ] && notes="0"
    [ "$projects" = "null" ] && projects="0"
    log_pass "Local API healthy ($notes notes, $projects projects)"
    return 0
  else
    log_fail "Local API unhealthy (status: $status)"
    return 1
  fi
}

test_remote_api() {
  log_test "Testing remote API at ${REMOTE_URL}"

  # Test public API endpoint (health requires OAuth)
  if ! response=$(curl -sf --connect-timeout 5 "${REMOTE_URL}/api/projects" 2>/dev/null); then
    log_warn "Remote API not responding at ${REMOTE_URL}/api/projects"
    log_info "This is optional if not using remote sync"
    return 1
  fi

  local project_count=$(echo "$response" | jq '.projects | length' 2>/dev/null || echo "0")
  log_pass "Remote API accessible ($project_count projects)"
  return 0
}

test_session() {
  log_test "Testing session management"

  if [ ! -f "$SESSION_FILE" ]; then
    log_fail "Session file not found at $SESSION_FILE"
    log_info "Run a Claude Code command to initialize a session"
    return 1
  fi

  local session_id=$(jq -r '.session_id' "$SESSION_FILE" 2>/dev/null || echo "")
  if [ -z "$session_id" ]; then
    log_fail "Session file exists but has no session_id"
    return 1
  fi

  log_info "Session ID: $session_id"

  # Test if session exists on backend
  if ! response=$(curl -sf "${API_URL}/api/sessions/${session_id}" 2>/dev/null); then
    log_fail "Session not found on backend"
    log_info "Session may need to be recreated. Try restarting Claude Code."
    return 1
  fi

  local status=$(echo "$response" | jq -r '.status' 2>/dev/null || echo "")
  local event_count=$(echo "$response" | jq -r '.event_count' 2>/dev/null || echo "0")

  if [ "$status" = "active" ]; then
    log_pass "Session active ($event_count events tracked)"
    return 0
  else
    log_warn "Session exists but status is: $status"
    return 1
  fi
}

test_mcp_config() {
  log_test "Testing MCP server configuration"

  local mcp_file="/home/redleif/Obsidian-Memory/.mcp.json"
  if [ ! -f "$mcp_file" ]; then
    log_fail "MCP configuration not found at $mcp_file"
    return 1
  fi

  local command=$(jq -r '.mcpServers."obsidian-memory".command' "$mcp_file" 2>/dev/null || echo "")
  if [ "$command" = "bun" ]; then
    log_fail "MCP configured to use 'bun' but bun is not installed"

    if [ "$FIX_MODE" = true ]; then
      log_fix "Updating .mcp.json to use 'npx tsx' instead of 'bun'"
      jq '.mcpServers."obsidian-memory".command = "npx" | .mcpServers."obsidian-memory".args = ["tsx", "src/index.ts"]' \
        "$mcp_file" > "${mcp_file}.tmp" && mv "${mcp_file}.tmp" "$mcp_file"
      log_pass "Fixed: MCP configuration updated"
    else
      log_info "Run with --fix to automatically update configuration"
    fi
    return 1
  elif [ "$command" = "npx" ]; then
    log_pass "MCP configuration uses npx tsx (correct)"
    return 0
  else
    log_warn "MCP uses unknown command: $command"
    return 1
  fi
}

test_mcp_server() {
  log_test "Testing MCP server startup"

  local mcp_dir="/home/redleif/Obsidian-Memory/mcp-server"
  if [ ! -d "$mcp_dir" ]; then
    log_fail "MCP server directory not found at $mcp_dir"
    return 1
  fi

  # Test if server can start
  if timeout 3 npx tsx "$mcp_dir/src/index.ts" >/dev/null 2>&1; then
    log_pass "MCP server can start successfully"
    return 0
  else
    log_fail "MCP server failed to start"
    log_info "Try: cd $mcp_dir && npx tsx src/index.ts"
    return 1
  fi
}

test_hooks() {
  log_test "Testing hook installation"

  local hooks_dir="/home/redleif/Obsidian-Memory/.claude/hooks"
  if [ ! -d "$hooks_dir" ]; then
    log_fail "Hooks directory not found at $hooks_dir"
    return 1
  fi

  local required_hooks=(
    "session-start.sh"
    "user-prompt-submit.sh"
    "post-tool-use-edits.sh"
    "pre-compact.sh"
    "session-end.sh"
    "_lib.sh"
  )

  local missing=0
  for hook in "${required_hooks[@]}"; do
    if [ ! -f "$hooks_dir/$hook" ]; then
      log_fail "Missing hook: $hook"
      missing=$((missing + 1))
    fi
  done

  if [ $missing -eq 0 ]; then
    log_pass "All hooks installed"
    return 0
  else
    log_fail "$missing hook(s) missing"
    return 1
  fi
}

test_om_cli() {
  log_test "Testing om.sh CLI helper"

  local om_script="/home/redleif/Obsidian-Memory/.claude/scripts/om.sh"
  if [ ! -f "$om_script" ]; then
    log_fail "om.sh not found at $om_script"
    return 1
  fi

  if ! "$om_script" health >/dev/null 2>&1; then
    log_fail "om.sh health check failed"
    return 1
  fi

  log_pass "om.sh CLI working"
  return 0
}

test_sync() {
  log_test "Testing local/remote sync status"

  local local_notes=$(curl -sf "${API_URL}/health" 2>/dev/null | jq -r '.notes.total // 0' 2>/dev/null || echo "0")
  local remote_projects=$(curl -sf "${REMOTE_URL}/api/projects" 2>/dev/null | jq '.projects | length' 2>/dev/null || echo "0")

  # Handle "null" string from jq
  [ "$local_notes" = "null" ] && local_notes="0"
  [ "$remote_projects" = "null" ] && remote_projects="0"

  if [ "$local_notes" -gt 0 ] 2>/dev/null && [ "$remote_projects" -gt 0 ] 2>/dev/null; then
    log_pass "Local and remote data present (local: $local_notes notes, remote: $remote_projects projects)"
    return 0
  else
    log_warn "Sync status unclear (local: $local_notes notes, remote: $remote_projects projects)"
    return 1
  fi
}

# ── Main ────────────────────────────────────────────────────────────

echo "═════════════════════════════════════════════════════════"
echo "  Obsidian-Memory Health Check"
echo "═════════════════════════════════════════════════════════"
echo ""

PASS=0
FAIL=0

run_test() {
  if "$1"; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi
  echo ""
}

run_test test_local_api
run_test test_session
run_test test_mcp_config
run_test test_mcp_server
run_test test_hooks
run_test test_om_cli
run_test test_remote_api
run_test test_sync

echo "═════════════════════════════════════════════════════════"
echo -e "  Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
echo "═════════════════════════════════════════════════════════"
echo ""

if [ $FAIL -gt 0 ]; then
  echo "Run with --fix to automatically fix configuration issues"
  echo "Run with --verbose for detailed diagnostics"
  exit 1
fi

exit 0
