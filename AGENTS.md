# Obsidian-Memory Operational Guide

## Project Overview

Unified memory management system for Claude Code with:
- FastAPI Python backend (app/)
- TypeScript MCP server (Bun) (mcp-server/src/)
- Next.js web UI (web-ui/src/)
- Claude Code hooks (hooks/)

## Build Commands

### Backend (Python/FastAPI)
```bash
cd backend
pip install -e ".[dev]"
pytest tests/ -v
mypy app/
ruff check app/
ruff format app/  # Auto-fix formatting
```

### MCP Server (TypeScript/Bun)
```bash
cd mcp-server
bun install
bun test
bun run typecheck
bun run lint
bun run lint:fix  # Auto-fix lint issues
bun run build
```

### Web UI (Next.js)
```bash
cd web-ui
npm ci
npm test
npm run typecheck
npm run lint
npm run lint:fix  # Auto-fix lint issues
npm run build
```

### Full Validation (Backpressure)
```bash
./scripts/test-all.sh           # Full check with builds
./scripts/test-all.sh --quick   # Skip builds
```

## Specifications

All specs are in `specs/` directory:
- `core-vault-manager.md` - Multi-vault file I/O
- `core-markdown-parser.md` - Frontmatter, observations, relations
- `core-search-index.md` - SQLite FTS5 search

## Patterns Discovered

<!-- Updated by Ralph during loops -->

## Common Failures

<!-- Updated by Ralph during loops -->

## Environment Setup

Required versions:
- Python 3.11+
- Bun 1.0+
- Node.js 20+
- SQLite 3.35+ (FTS5 support)

### Initial Setup
```bash
# Backend
cd backend && pip install -e ".[dev]"

# MCP Server
cd mcp-server && bun install

# Web UI
cd web-ui && npm ci
```

## Key Files

- `IMPLEMENTATION_PLAN.md` - Current task tracking
- `PROMPT_plan.md` - Planning mode instructions
- `PROMPT_build.md` - Building mode instructions
- `specs/*.md` - Feature specifications
- `.taskmaster/docs/prd.md` - Product requirements
