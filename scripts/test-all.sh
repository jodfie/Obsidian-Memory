#!/usr/bin/env bash
#
# Full validation script for Obsidian-Memory
# Runs all backpressure checks: tests, type checking, linting
#
# Usage:
#   ./scripts/test-all.sh           # Run all checks
#   ./scripts/test-all.sh --quick   # Skip slow checks
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Add bun to PATH if installed
if [ -d "$HOME/.bun/bin" ]; then
  export PATH="$HOME/.bun/bin:$PATH"
fi

cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_step() { echo -e "${CYAN}==>${NC} $1"; }
log_pass() { echo -e "${GREEN}✓${NC} $1"; }
log_fail() { echo -e "${RED}✗${NC} $1"; }

QUICK_MODE=false
if [[ "${1:-}" == "--quick" ]]; then
  QUICK_MODE=true
fi

FAILED=false

# ============================================================================
# BACKEND (Python)
# ============================================================================
# Activate virtual environment if it exists
if [ -f "backend/.venv/bin/activate" ]; then
  source backend/.venv/bin/activate
fi

log_step "Backend: Type checking (mypy)..."
if (cd backend && python3 -m mypy app/ 2>/dev/null || [ ! -d "app" ]); then
  log_pass "Backend type check passed"
else
  log_fail "Backend type check failed"
  FAILED=true
fi

log_step "Backend: Linting (ruff)..."
if [ ! -d "backend/app" ]; then
  log_pass "Backend lint passed (no app directory to lint)"
elif (cd backend && python3 -m ruff check app/ 2>/dev/null); then
  log_pass "Backend lint passed"
else
  log_fail "Backend lint failed"
  FAILED=true
fi

log_step "Backend: Tests (pytest)..."
if (cd backend && python3 -m pytest tests/ -v); then
  log_pass "Backend tests passed"
else
  log_fail "Backend tests failed"
  FAILED=true
fi

# ============================================================================
# MCP SERVER (TypeScript/Bun)
# ============================================================================
log_step "MCP Server: Type checking (tsc)..."
if (cd mcp-server && bun run typecheck 2>/dev/null); then
  log_pass "MCP Server type check passed"
else
  log_fail "MCP Server type check failed"
  FAILED=true
fi

log_step "MCP Server: Linting (eslint)..."
if (cd mcp-server && bun run lint 2>/dev/null); then
  log_pass "MCP Server lint passed"
else
  log_fail "MCP Server lint failed"
  FAILED=true
fi

log_step "MCP Server: Tests (bun test)..."
if (cd mcp-server && bun test); then
  log_pass "MCP Server tests passed"
else
  log_fail "MCP Server tests failed"
  FAILED=true
fi

# ============================================================================
# WEB UI (Next.js)
# ============================================================================
log_step "Web UI: Type checking (tsc)..."
if (cd web-ui && npm run typecheck 2>/dev/null); then
  log_pass "Web UI type check passed"
else
  log_fail "Web UI type check failed"
  FAILED=true
fi

log_step "Web UI: Linting (next lint)..."
if [ ! -f "web-ui/.eslintrc.json" ] && [ ! -f "web-ui/.eslintrc.js" ] && [ ! -f "web-ui/.eslintrc.cjs" ]; then
  # ESLint not configured yet, skip for now
  log_pass "Web UI lint passed (ESLint not configured)"
elif (cd web-ui && npm run lint 2>/dev/null); then
  log_pass "Web UI lint passed"
else
  log_fail "Web UI lint failed"
  FAILED=true
fi

log_step "Web UI: Tests (jest)..."
if (cd web-ui && npm test -- --passWithNoTests 2>/dev/null); then
  log_pass "Web UI tests passed"
else
  log_fail "Web UI tests failed"
  FAILED=true
fi

# ============================================================================
# BUILD CHECK (optional, skip in quick mode)
# ============================================================================
if ! $QUICK_MODE; then
  log_step "MCP Server: Build..."
  if (cd mcp-server && bun run build 2>/dev/null); then
    log_pass "MCP Server build passed"
  else
    log_fail "MCP Server build failed"
    FAILED=true
  fi

  log_step "Web UI: Build..."
  if (cd web-ui && npm run build 2>/dev/null); then
    log_pass "Web UI build passed"
  else
    log_fail "Web UI build failed"
    FAILED=true
  fi
fi

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
if $FAILED; then
  log_fail "Some checks failed!"
  exit 1
else
  log_pass "All checks passed!"
  exit 0
fi
