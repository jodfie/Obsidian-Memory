#!/usr/bin/env bash
# update-remote-om.sh -- Push latest OM hooks + om.sh to remote servers
#
# Quick usage:
#   ./scripts/update-remote-om.sh                    # update all servers in SERVERS list
#   ./scripts/update-remote-om.sh user@host          # update a single server
#   ./scripts/update-remote-om.sh user1@h1 user2@h2  # update specific servers
#
# Servers list: Edit the SERVERS array below, or pass targets as arguments.
# This only pushes hooks and om.sh — it does NOT install Claude Code or other tools.

set -euo pipefail

# ── Default server list ─────────────────────────────────────────────
# Format: "user@hostname" (must be reachable via SSH)
# Edit this list to match your machines.
SERVERS=(
  # "user@hostname"
)

# ── Resolve script paths ────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_SRC="$REPO_DIR/.claude/hooks"
SCRIPTS_SRC="$REPO_DIR/.claude/scripts"

HOOK_FILES=(
  _lib.sh
  session-start.sh
  session-end.sh
  user-prompt-submit.sh
  post-tool-use-edits.sh
  post-tool-use-search.sh
  pre-compact.sh
  stop.sh
)

# Allow filtering to specific files
SCRIPT_FILES=(
  om.sh
)

# ── Helpers ──────────────────────────────────────────────────────────
ok()   { echo "  [OK]    $*"; }
err()  { echo "  [FAIL]  $*" >&2; }
info() { echo "  [INFO]  $*"; }

# ── Determine targets ───────────────────────────────────────────────
if [ $# -gt 0 ]; then
  TARGETS=("$@")
else
  if [ ${#SERVERS[@]} -eq 0 ]; then
    echo "No servers configured. Either:"
    echo "  1. Edit SERVERS array in this script"
    echo "  2. Pass targets as arguments: $0 user@host1 user@host2"
    exit 1
  fi
  TARGETS=("${SERVERS[@]}")
fi

# ── Version info ─────────────────────────────────────────────────────
VERSION=$(cd "$REPO_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "Obsidian-Memory hook update (commit: $VERSION)"
echo "Updating ${#TARGETS[@]} server(s)..."
echo ""

# ── Push to each server ─────────────────────────────────────────────
SUCCEEDED=0
FAILED=0

for target in "${TARGETS[@]}"; do
  user="${target%%@*}"
  host="${target##*@}"
  remote_hooks="/home/${user}/.claude/hooks"
  remote_scripts="/home/${user}/.claude/scripts"

  echo "--- $host ($user) ---"

  # Test connectivity
  if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$target" "true" 2>/dev/null; then
    err "Cannot connect to $target (SSH failed)"
    FAILED=$((FAILED + 1))
    continue
  fi

  # Ensure directories exist
  ssh -o ConnectTimeout=5 "$target" "mkdir -p $remote_hooks $remote_scripts" 2>/dev/null

  # Push hooks
  hook_ok=true
  for f in "${HOOK_FILES[@]}"; do
    if [ -f "$HOOKS_SRC/$f" ]; then
      cat "$HOOKS_SRC/$f" | ssh -o ConnectTimeout=5 "$target" "cat > $remote_hooks/$f && chmod +x $remote_hooks/$f" 2>/dev/null
      if [ $? -ne 0 ]; then
        err "Failed to push $f"
        hook_ok=false
      fi
    fi
  done

  # Push scripts
  for f in "${SCRIPT_FILES[@]}"; do
    if [ -f "$SCRIPTS_SRC/$f" ]; then
      cat "$SCRIPTS_SRC/$f" | ssh -o ConnectTimeout=5 "$target" "cat > $remote_scripts/$f && chmod +x $remote_scripts/$f" 2>/dev/null
    fi
  done

  if $hook_ok; then
    ok "Updated ($VERSION)"
    SUCCEEDED=$((SUCCEEDED + 1))
  else
    err "Partial update"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "Done: $SUCCEEDED succeeded, $FAILED failed"
[ $FAILED -eq 0 ] || exit 1
