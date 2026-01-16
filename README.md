# Obsidian-Memory

Unified memory management system for Claude Code combining:
- Hook-based auto-capture (cc-obsidian-mem)
- Knowledge graph navigation (Basic Memory)
- Cross-project context library (OpenContext)
- Heavy AI processing for entity/relation extraction

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code (Hooks) │ Claude.ai (MCP/SSE) │ Web UI (Browser)  │
└──────────┬───────────┴─────────┬───────────┴────────┬──────────┘
           │                     │                    │
           ▼                     ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Server (TypeScript/Bun)                │
│  mem_read │ mem_write │ mem_search │ graph_traverse │ ...      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                     │
│  Vault Manager │ Graph Engine │ AI Processor │ Search Index    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Storage: Markdown (truth) + SQLite (index)         │
└─────────────────────────────────────────────────────────────────┘
```

## Development

This project uses the Ralph Wiggum technique for AI-driven development.

### Quick Start

```bash
# Plan mode - analyze gaps and create TODO
./loop.sh plan

# Build mode - implement tasks iteratively
./loop.sh

# Limited iterations
./loop.sh 20
```

### Manual Development

```bash
# Backend
cd backend && pip install -e ".[dev]" && pytest

# MCP Server
cd mcp-server && bun install && bun test

# Web UI
cd web-ui && npm ci && npm test
```

## Project Structure

```
obsidian-memory/
├── specs/              # Specification documents (one per topic)
├── backend/            # FastAPI Python backend
├── mcp-server/         # TypeScript MCP server
├── web-ui/             # Next.js frontend
├── hooks/              # Claude Code lifecycle hooks
├── AGENTS.md           # Operational guide (Ralph Wiggum)
├── IMPLEMENTATION_PLAN.md  # Task tracking
├── PROMPT_plan.md      # Planning mode prompt
├── PROMPT_build.md     # Building mode prompt
└── loop.sh             # Ralph Wiggum loop script
```

## License

MIT
