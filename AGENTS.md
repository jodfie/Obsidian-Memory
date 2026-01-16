# Obsidian-Memory Operational Guide

## Project Overview

Unified memory management system for Claude Code with:
- FastAPI Python backend
- TypeScript MCP server (Bun)
- Next.js web UI
- Claude Code hooks

## Build Commands

### Backend (Python/FastAPI)
```bash
cd backend
pip install -e ".[dev]"
pytest tests/ -v
mypy app/
ruff check app/
```

### MCP Server (TypeScript/Bun)
```bash
cd mcp-server
bun install
bun test
bun run typecheck
bun run lint
```

### Web UI (Next.js)
```bash
cd web-ui
npm ci
npm test
npm run typecheck
npm run lint
npm run build
```

### Full Validation
```bash
./scripts/test-all.sh
```

## Patterns Discovered

<!-- Updated by Ralph during loops -->

## Common Failures

<!-- Updated by Ralph during loops -->

## Environment Setup

- Python 3.11+
- Bun 1.0+
- Node.js 20+
- SQLite 3.35+ (FTS5 support)
