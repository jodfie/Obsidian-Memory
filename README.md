# Obsidian-Memory

Unified memory management system for Claude Code combining:
- Hook-based auto-capture (cc-obsidian-mem)
- Knowledge graph navigation (Basic Memory)
- Cross-project context library (OpenContext)
- Heavy AI processing for entity/relation extraction

## Features

- **Multi-Vault Support**: Manage multiple Obsidian vaults from a single interface
- **Knowledge Graph**: Automatic graph construction from markdown notes with wikilinks and relations
- **Full-Text Search**: SQLite FTS5-powered search across all notes
- **AI Processing**: Entity extraction, relation inference, and session summarization using Claude API
- **Session Tracking**: Automatic capture of Claude Code sessions with AI-powered summaries
- **Project Management**: Organize notes by project with context switching
- **Cross-Device Sync**: Git-based synchronization with device tracking
- **Web UI**: Modern Next.js interface for browsing and editing notes
- **MCP Integration**: Model Context Protocol server for Claude Code and Claude.ai

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

## Quick Start

### Prerequisites

- Python 3.11+
- Bun 1.0+ (for MCP server)
- Node.js 20+ (for Web UI)
- Git (for sync features)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/jodfie/Obsidian-Memory.git
   cd Obsidian-Memory
   ```

2. **Backend Setup**
   ```bash
   cd backend
   pip install -e ".[dev]"
   ```

3. **MCP Server Setup**
   ```bash
   cd mcp-server
   bun install
   ```

4. **Web UI Setup**
   ```bash
   cd web-ui
   npm ci
   ```

### Running with Docker

The easiest way to run the full stack:

```bash
docker-compose up -d
```

This starts:
- Backend API on `http://localhost:8000`
- Web UI on `http://localhost:3000`
- MCP server (stdio mode)

See [docs/deployment.md](docs/deployment.md) for detailed Docker instructions.

### Manual Development

```bash
# Backend
cd backend
uvicorn app.main:app --reload

# MCP Server (stdio mode for Claude Code)
cd mcp-server
bun run src/index.ts

# Web UI
cd web-ui
npm run dev
```

## Configuration

### Backend Configuration

Create `~/.obsidian-memory/config.json`:

```json
{
  "vaults": [
    {
      "name": "my-vault",
      "path": "/path/to/vault"
    }
  ]
}
```

Environment variables (see `backend/app/config.py`):
- `API_TITLE` - API title (default: "Obsidian-Memory")
- `LOG_LEVEL` - Logging level (default: "INFO")
- `REQUIRE_AUTH` - Enable Bearer token auth (default: false)
- `API_TOKEN` - Bearer token for authentication
- `ANTHROPIC_API_KEY` - Claude API key for AI features
- `CLOUDFLARE_ACCESS_ENABLED` - Enable Cloudflare Access (default: false)

### MCP Server Configuration

Environment variables:
- `MCP_TRANSPORT` - Transport type: `stdio` (default) or `sse`
- `MCP_SSE_PORT` - Port for SSE server (default: 3000)
- `OBSIDIAN_MEMORY_API_URL` - Backend API URL (default: `http://localhost:8000`)
- `OBSIDIAN_MEMORY_API_TOKEN` - Bearer token (if auth enabled)

### Web UI Configuration

Environment variables:
- `NEXT_PUBLIC_API_URL` - Backend API URL (default: `http://localhost:8000`)

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints

- `GET /health` - Health check
- `GET /metrics` - System metrics (CPU, memory, threads)
- `GET /api/notes` - List notes
- `POST /api/notes` - Create note
- `GET /api/notes/{id}` - Get note
- `PUT /api/notes/{id}` - Update note
- `DELETE /api/notes/{id}` - Delete note
- `POST /api/notes/search` - Search notes
- `GET /api/graph` - Get knowledge graph
- `GET /api/projects` - List projects
- `GET /api/sessions` - List sessions
- `GET /api/sync/status/{vault_name}` - Get sync status

See [docs/api.md](docs/api.md) for complete API documentation.

## MCP Tools

The MCP server provides the following tools:

### Memory Tools
- `mem_read` - Read a note by ID, permalink, or search
- `mem_write` - Create or update a note
- `mem_search` - Search notes with filters

### Graph Tools
- `graph_traverse` - Traverse the knowledge graph
- `graph_similar` - Find similar notes

### Project Tools
- `project_list` - List all projects
- `project_switch` - Switch to a project context
- `project_create` - Create a new project

### Session Tools
- `session_observe` - Add an observation/event to a session
- `session_summary` - Generate AI summary of a session
- `session_context` - Get session context

### Context Tools
- `build_context` - Build context from memory:// URIs

See [mcp-server/README.md](mcp-server/README.md) for detailed MCP documentation.

## Claude Code Hooks

The `hooks/` directory contains lifecycle hooks for Claude Code:

- `session-start.sh` - Loads project context and recent memories
- `user-prompt-submit.sh` - Logs user prompts
- `post-tool-use.sh` - Captures tool usage and file edits
- `pre-compact.sh` - Triggers AI summarization
- `session-end.sh` - Finalizes session and extracts patterns

See [hooks/README.md](hooks/README.md) for hook configuration.

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
cd backend
pip install -e ".[dev]"
pytest

# MCP Server
cd mcp-server
bun install
bun test

# Web UI
cd web-ui
npm ci
npm test
```

### Full Validation

```bash
./scripts/test-all.sh
```

## Project Structure

```
obsidian-memory/
├── specs/              # Specification documents
├── backend/            # FastAPI Python backend
│   ├── app/
│   │   ├── api/        # API endpoints
│   │   ├── models/     # Pydantic models
│   │   ├── services/   # Business logic
│   │   ├── middleware/ # Middleware (auth, logging, etc.)
│   │   └── utils/       # Utilities
│   └── tests/          # Test suite
├── mcp-server/         # TypeScript MCP server
│   ├── src/
│   │   ├── tools/      # MCP tool implementations
│   │   └── transport/  # Transport implementations
│   └── tests/
├── web-ui/             # Next.js frontend
│   ├── src/
│   │   ├── app/        # Next.js app router pages
│   │   ├── components/ # React components
│   │   └── lib/        # Utilities and API client
│   └── tests/
├── hooks/              # Claude Code lifecycle hooks
├── docs/               # Additional documentation
├── docker-compose.yml  # Docker Compose configuration
├── AGENTS.md           # Operational guide (Ralph Wiggum)
├── IMPLEMENTATION_PLAN.md  # Task tracking
└── README.md           # This file
```

## Deployment

### Quick Start

**Development:**
```bash
cp .env.dev.example .env.dev
# Edit .env.dev
make dev
# Access at https://memory-dev.redleif.dev
```

**Production:**
```bash
cp .env.prod.example .env.prod
# Edit .env.prod with production values
make prod
# Access at https://memory.redleif.dev
```

### Detailed Deployment Guide

See [DEPLOY.md](DEPLOY.md) for complete deployment instructions including:
- Environment configuration
- Traefik setup
- CI/CD workflows
- Troubleshooting
- Security checklist

### Docker Deployment (Legacy)

See [docs/deployment.md](docs/deployment.md) for legacy Docker deployment instructions.

### Production Considerations

- Set `REQUIRE_AUTH=true` and configure `API_TOKEN`
- Configure `ANTHROPIC_API_KEY` for AI features
- Set up proper logging (logs in `~/.obsidian-memory/logs/`)
- Configure Cloudflare Access if needed
- Set up Git sync for vaults
- Monitor `/metrics` endpoint

## Monitoring

- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics` (CPU, memory, threads)
- **Logs**: Structured JSON logs in `~/.obsidian-memory/logs/obsidian-memory.log`
- **Log Rotation**: Automatic (10MB files, 5 backups)

## Security

- Bearer token authentication (optional)
- Cloudflare Access integration (optional)
- Non-root Docker containers
- Path validation to prevent directory traversal
- Atomic file writes

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `./scripts/test-all.sh`
5. Submit a pull request

## License

MIT

## Documentation

📚 **Comprehensive documentation available in [docs/](docs/)**

### Quick Links

| For... | Start Here |
|--------|------------|
| 🚀 **New Users** | [Quick Start Guide](docs/QUICK-START.md) |
| 🤖 **AI Models** | [AI Reference Card](docs/AI-REFERENCE.md) |
| 🔗 **Claude.ai Users** | [Claude.ai Integration](docs/CLAUDE-AI-INTEGRATION.md) |
| 🏗️ **Developers** | [Architecture Guide](docs/ARCHITECTURE.md) |
| 🔧 **Troubleshooting** | [Problem Solving Guide](docs/TROUBLESHOOTING.md) |
| 📖 **Full Index** | [Documentation Index](docs/README.md) |

### Additional Resources

- [API Documentation](docs/api.md) - Complete REST API reference
- [MCP Integration](docs/mcp-integration.md) - Cursor and Claude.ai setup
- [Authentication](docs/AUTHENTICATION.md) - Auth methods and security
- [Deployment Guide](docs/deployment.md) - Production deployment
- [MCP Server README](mcp-server/README.md) - MCP server details
- [Hooks README](hooks/README.md) - Claude Code hooks
- [Secret Management](docs/secret-management-best-practices.md) - Security best practices
