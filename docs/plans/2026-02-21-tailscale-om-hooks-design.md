# Tailscale OM Hook Connectivity

**Date:** 2026-02-21
**Status:** Implemented

## Problem

Claude Code sessions on remote VPS machines had no way to report activity back to the Obsidian-Memory API running on redleif-hostinger. The API was bound to `127.0.0.1:8765` only.

## Solution

Use Tailscale mesh VPN to connect all machines. Bind the OM API and MCP server to the Tailscale interface alongside localhost. Deploy hooks and CLI tools to remote machines via a setup script.

## Changes

### redleif-hostinger (OM host)

**docker-compose.prod.yml** — added Tailscale port bindings:
- `100.99.29.82:8765:8765` (API for hooks/om.sh)
- `100.99.29.82:8738:3000` (MCP SSE for Claude Desktop/Cursor)
- Locked down MCP from `0.0.0.0:8738` to localhost + Tailscale only

### Remote machines

Created `scripts/setup-remote-om.sh` which:
1. Verifies Tailscale connectivity
2. Installs Claude Code, Codex, and Happy if missing
3. Deploys OM hooks to `~/.claude/hooks/` (user-level, fires for all projects)
4. Deploys `om.sh` CLI to `~/.claude/scripts/`
5. Sets `OBSIDIAN_MEMORY_API_URL=http://redleif-hostinger:8765` in shell profile
6. Configures Claude Code hook settings in `~/.claude/settings.json`

### Deployment results

| Server | Tailscale IP | Claude | Codex | Happy | Hooks |
|--------|-------------|--------|-------|-------|-------|
| cps-vps | 100.85.35.2 | 2.0.76 (existing) | failed (npm perms) | 0.13.0 (existing) | deployed |
| redleif-contabo | 100.125.155.44 | 2.0.30 (existing) | installed | installed | deployed |
| trunk-chatham | 100.100.69.74 | 2.1.50 (installed) | installed | installed | deployed |
| ga-scanner-cloud | 100.82.38.18 | 2.1.50 (installed) | failed (npm perms) | failed (npm perms) | deployed |

### MacBook Air (deferred)

Instructions saved to OM note #928 for later setup. Supports Claude Desktop, Cursor, and Claude Code via Tailscale.

## Security

- No auth tokens or headers needed — Tailscale WireGuard encryption handles it
- API only reachable from tailnet devices (100.x.x.x)
- claude.ai MCP unaffected — uses Cloudflare tunnel (Docker internal network), not host port binding
- MCP server no longer exposed on `0.0.0.0` (was a security improvement)

## Architecture

```
Remote VPS (Claude Code)
  └─ hooks (curl) ──── Tailscale WireGuard ────┐
                                                 │
redleif-hostinger                                │
  ├─ 127.0.0.1:8765 ← local access              │
  ├─ 100.99.29.82:8765 ← tailnet access ────────┘
  ├─ 127.0.0.1:8738 ← local MCP
  ├─ 100.99.29.82:8738 ← tailnet MCP (Claude Desktop/Cursor)
  └─ Traefik → Docker internal → memory:8765 ← claude.ai (Cloudflare tunnel)
```
