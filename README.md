# Obsidian-Memory

A persistent memory system for AI coding agents. Obsidian-Memory captures sessions, decisions, and knowledge from Claude Code (and other MCP-compatible tools) into a searchable knowledge base backed by Obsidian-style markdown and a SQLite index.

**Key idea**: Your AI assistant forgets everything between sessions. Obsidian-Memory fixes that.

## Features

- **Automatic Session Capture** — Claude Code hooks log prompts, edits, and searches without manual effort
- **Knowledge Graph** — Automatic graph from markdown wikilinks and AI-extracted relations
- **Full-Text Search** — SQLite FTS5-powered search across all notes
- **AI Summarization** — Session summaries, entity extraction, and pattern detection via Claude API
- **MCP Integration** — Model Context Protocol server supporting stdio (Claude Code), SSE (Claude.ai), and HTTP (Cursor)
- **Multi-Project** — Organize notes by project with context switching
- **SilverBullet Editor** — Web-based markdown editor with live sync to the index
- **Cross-Device Sync** — Git-based vault synchronization

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code (Hooks) │ Claude.ai (MCP/SSE) │ SilverBullet (Web)│
└──────────┬───────────┴─────────┬───────────┴────────┬──────────┘
           │                     │                    │
           ▼                     ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server (TypeScript/Bun)                   │
│  mem_read │ mem_write │ mem_search │ graph_traverse │ ...       │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python 3.12)                  │
│  Notes API │ Graph Engine │ AI Processor │ Session Tracker       │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│            Markdown Vaults (truth) + SQLite Index (search)       │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/jodfie/Obsidian-Memory.git
cd Obsidian-Memory
cp .env.example .env
# Edit .env — set VAULT_PATH at minimum
docker compose up -d
```

This starts:
- **Backend API** on `http://localhost:8765`
- **MCP Server** (stdio mode for Claude Code)
- **SilverBullet** on `http://localhost:3001` (dev) or `3100` (prod)

API docs available at `http://localhost:8765/docs` (Swagger) or `/redoc`.

### Production with Traefik

```bash
cp .env.prod.example .env.prod
# Edit .env.prod with your domain, auth settings, etc.
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

See [docs/deployment.md](docs/deployment.md) for full production setup including Traefik, OAuth, and Cloudflare Access.

### Makefile Shortcuts

```bash
make setup    # Copy env templates
make dev      # Start development stack
make prod     # Start production stack
make logs     # View logs
make health   # Health check
```

## Claude Code Integration

### Hook Setup (Remote Machines)

Deploy Obsidian-Memory hooks to any machine running Claude Code with a single command:

```bash
OM_HOST=your-om-server bash -c "$(curl -fsSL https://raw.githubusercontent.com/jodfie/Obsidian-Memory/main/scripts/setup-remote-om.sh)"
```

This installs Claude Code (if needed) and deploys hooks that automatically:
- Create an OM session on startup
- Log every user prompt, file edit, and search
- Trigger AI summarization before context compaction
- Warn loudly if the OM backend is unreachable or sessions go stale

**Requirements**: Node.js 20+, Tailscale (for connecting to OM host), `jq`, `curl`.

### Hook Setup (Local / This Repo)

Hooks are already in `.claude/hooks/`. Just set the API URL:

```bash
echo 'export OBSIDIAN_MEMORY_API_URL="http://localhost:8765"' >> ~/.bashrc
source ~/.bashrc
```

### CLI Helper

The `om.sh` script provides direct API access without MCP:

```bash
# Write a note
.claude/scripts/om.sh write --title "Design Decision" --content "Chose X over Y because..." --project MyProject --type decision

# Search
.claude/scripts/om.sh search "authentication" --project MyProject --limit 10

# Read
.claude/scripts/om.sh read --id 123

# Other: update, delete, supersede, projects, health
.claude/scripts/om.sh help
```

## MCP Tools

The MCP server exposes 13 tools across 5 categories:

| Category | Tools | Description |
|----------|-------|-------------|
| **Memory** | `mem_read`, `mem_write`, `mem_search`, `mem_supersede` | Note CRUD and search |
| **Graph** | `graph_traverse`, `graph_similar` | Knowledge graph navigation |
| **Project** | `project_list`, `project_switch`, `project_create` | Project context management |
| **Session** | `session_observe`, `session_summary`, `session_context` | Session tracking |
| **Context** | `build_context` | Build context from memory:// URIs |

### Connecting Claude Code

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "command": "docker",
      "args": ["exec", "-i", "memory-mcp", "node", "dist/index.js"],
      "env": {}
    }
  }
}
```

See [docs/mcp-integration.md](docs/mcp-integration.md) for Claude.ai (SSE) and Cursor (HTTP) setup.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /metrics` | System metrics |
| `GET/POST /api/notes` | List / create notes |
| `GET/PUT/DELETE /api/notes/{id}` | Note CRUD |
| `POST /api/notes/search` | Full-text search |
| `GET /api/graph` | Knowledge graph |
| `GET /api/projects` | List projects |
| `POST /api/sessions` | Create session |
| `GET /api/sessions/{id}` | Get session |
| `POST /api/sessions/observe` | Log observation |
| `POST /api/sessions/{id}/summary` | Generate summary |

Full reference: [docs/api.md](docs/api.md)

## Configuration

### Environment Variables

Copy `.env.example` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `VAULT_PATH` | — | Path to your Obsidian vault(s) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `REQUIRE_AUTH` | `false` | Enable Bearer token auth |
| `API_TOKEN` | — | Bearer token (if auth enabled) |
| `ANTHROPIC_API_KEY` | — | Claude API key for AI features |
| `BASE_DOMAIN` | — | Production domain |
| `TAILSCALE_IP` | — | Tailscale IP for remote hook access |

See `.env.example` for the full list including Cloudflare Access, Supabase, and OAuth options.

## Project Structure

```
obsidian-memory/
├── backend/            # FastAPI Python backend
│   ├── app/
│   │   ├── api/        # REST endpoints
│   │   ├── models/     # Pydantic models
│   │   ├── services/   # Business logic
│   │   └── middleware/  # Auth, rate limiting, logging
│   └── tests/
├── mcp-server/         # TypeScript MCP server (Bun)
│   └── src/
│       ├── tools/      # MCP tool implementations
│       └── transport/  # stdio, SSE, HTTP adapters
├── web-ui/             # Next.js frontend (legacy)
├── .claude/
│   ├── hooks/          # Claude Code lifecycle hooks
│   └── scripts/        # om.sh CLI helper
├── scripts/            # Deployment and setup scripts
├── docs/               # Documentation
├── docker-compose.yml          # Base Docker config
├── docker-compose.dev.yml      # Dev overrides
├── docker-compose.prod.yml     # Production (Traefik, OAuth)
├── docker-compose.tailscale.yml # Optional Tailscale overlay
└── Makefile
```

## Monitoring

- **Health**: `GET /health`
- **Metrics**: `GET /metrics` (CPU, memory, uptime)
- **Logs**: Structured JSON in container stdout, rotated at 10MB x 5 backups
- **Hook warnings**: `[obsidian-memory] WARNING:` in Claude Code stderr when sessions go stale or API is unreachable

## Security

- Bearer token authentication (optional, recommended for production)
- Cloudflare Access integration (optional)
- OAuth2 proxy support
- Non-root Docker containers
- Path validation against directory traversal
- Rate limiting (70 req/min default)

## Documentation

| For... | Start Here |
|--------|------------|
| New Users | [Quick Start Guide](docs/QUICK-START.md) |
| AI Models | [AI Reference Card](docs/AI-REFERENCE.md) |
| Claude.ai Users | [Claude.ai Integration](docs/CLAUDE-AI-INTEGRATION.md) |
| Developers | [Architecture Guide](docs/ARCHITECTURE.md) |
| Troubleshooting | [Problem Solving Guide](docs/TROUBLESHOOTING.md) |
| Full Index | [Documentation Index](docs/README.md) |

Additional: [API Reference](docs/api.md) | [MCP Integration](docs/mcp-integration.md) | [Authentication](docs/AUTHENTICATION.md) | [Deployment](docs/deployment.md) | [Cloudflare Access](docs/cloudflare-access-setup.md)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `./scripts/test-all.sh`
5. Submit a pull request

## License

MIT
