#!/usr/bin/env bash
#
# Server-side deployment script for Obsidian-Memory production.
# Run this on the server (or as if on another server) after cloning/pulling.
#
# Usage:
#   ./scripts/deploy-server.sh           # Deploy prod (pull + up)
#   ./scripts/deploy-server.sh --no-pull # Deploy without git pull
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_step() { echo -e "${CYAN}==>${NC} $1"; }

DO_PULL=true
for arg in "$@"; do
  case "$arg" in
    --no-pull) DO_PULL=false ;;
  esac
done

# 1. Ensure Docker and Compose
log_step "Checking Docker and Compose..."
if ! command -v docker &>/dev/null; then
  log_warn "Docker not found. Install Docker and Docker Compose first."
  exit 1
fi
if ! docker compose version &>/dev/null && ! docker-compose version &>/dev/null; then
  log_warn "Docker Compose not found. Install Docker Compose."
  exit 1
fi
log_info "Docker OK"

# 2. Ensure proxy network (required by Traefik)
log_step "Ensuring Docker network 'proxy'..."
if ! docker network inspect proxy &>/dev/null; then
  docker network create proxy
  log_info "Created network 'proxy'"
else
  log_info "Network 'proxy' exists"
fi

# 3. Optional git pull
if [ "$DO_PULL" = true ]; then
  log_step "Pulling latest code..."
  if git rev-parse --git-dir &>/dev/null; then
    git pull origin main 2>/dev/null || git pull origin dev 2>/dev/null || true
    log_info "Pull done"
  else
    log_warn "Not a git repo; skipping pull"
  fi
else
  log_info "Skipping git pull (--no-pull)"
fi

# 4. Ensure .env.prod exists
log_step "Checking .env.prod..."
if [ ! -f .env.prod ]; then
  if [ -f .env.prod.example ]; then
    cp .env.prod.example .env.prod
    log_warn "Created .env.prod from .env.prod.example — EDIT IT with real secrets before first deploy."
    log_warn "Required: API_TOKEN, CLOUDFLARE_* if using Access, ANTHROPIC_API_KEY if using AI, CLOUDFLARE_TUNNEL_TOKEN if using tunnel."
  else
    echo -e "${RED}[ERROR]${NC} No .env.prod or .env.prod.example found."
    exit 1
  fi
fi

# 5. Build and start production stack
log_step "Building and starting production (memory, memory-mcp, web-ui, cloudflared)..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build

log_step "Waiting for health..."
sleep 5
docker ps --filter "name=memory" --format "table {{.Names}}\t{{.Status}}"

log_info "Deploy complete."
echo ""
echo "  API:    https://memory.example.com"
echo "  Web UI: https://app.memory.example.com"
echo "  Health: https://memory.example.com/health"
echo ""
echo "If app.memory.example.com is new: add DNS, Cloudflare Access app, and tunnel route (see DEPLOY.md)."
