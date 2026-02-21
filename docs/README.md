# Obsidian-Memory Documentation

Comprehensive documentation for Obsidian-Memory - a unified memory management system for AI assistants.

## Quick Navigation

| Document | Description |
|----------|-------------|
| [Quick Start](QUICK-START.md) | Get started in 5 minutes |
| [Architecture](ARCHITECTURE.md) | System architecture and design |
| [API Reference](api.md) | Complete REST API documentation |
| [MCP Integration](mcp-integration.md) | MCP server setup for Cursor and Claude.ai |
| [Claude.ai Setup](CLAUDE-AI-INTEGRATION.md) | Step-by-step Claude.ai integration |
| [Authentication](AUTHENTICATION.md) | Auth methods (Bearer, Cloudflare, OAuth) |
| [Deployment](deployment.md) | Docker and production deployment |
| [Troubleshooting](TROUBLESHOOTING.md) | Common issues and solutions |

## What is Obsidian-Memory?

Obsidian-Memory is a persistent memory system that enables AI assistants (Claude, GPT, etc.) to:

- **Store and retrieve knowledge** across sessions
- **Build knowledge graphs** from markdown notes with wikilinks
- **Track sessions** with automatic AI summarization
- **Search content** using full-text search (FTS5)
- **Sync across devices** via Git integration

## Architecture Overview

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

## Key Concepts

### Vaults
Obsidian vaults are directories containing markdown files. Multiple vaults can be registered and managed simultaneously.

### Notes
Markdown files with YAML frontmatter. Notes are indexed for search and linked via wikilinks.

### Projects
Logical groupings of notes. Used to scope sessions and context.

### Sessions
Time-bounded interactions with the system. Sessions track events and can be summarized by AI.

### Knowledge Graph
Nodes (notes) connected by edges (wikilinks, relations). Enables graph traversal and similarity search.

## Integration Methods

### 1. Claude Code (Local)
Uses stdio transport. Hooks auto-capture session data.

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "command": "bun",
      "args": ["run", "/path/to/mcp-server/src/index.ts"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "OBSIDIAN_MEMORY_API_URL": "http://localhost:8765"
      }
    }
  }
}
```

### 2. Claude.ai (Remote)
Uses SSE transport with OAuth 2.0 authentication via Cloudflare Access.

- **Server URL**: `https://memory.example.com/mcp`
- **OAuth Provider**: Cloudflare Access OIDC
- See [Claude.ai Integration](CLAUDE-AI-INTEGRATION.md) for setup

### 3. Cursor IDE
Uses Streamable HTTP transport.

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "url": "https://memory.example.com/mcp"
    }
  }
}
```

### 4. Web UI
React-based interface for browsing and editing notes.

## MCP Tools Reference

### Memory Tools
| Tool | Description |
|------|-------------|
| `mem_read` | Read note by ID, permalink, or search |
| `mem_write` | Create or update a note |
| `mem_search` | Search notes with filters |
| `mem_supersede` | Mark note as superseded |

### Graph Tools
| Tool | Description |
|------|-------------|
| `graph_traverse` | BFS/DFS graph traversal |
| `graph_similar` | Find similar notes |

### Project Tools
| Tool | Description |
|------|-------------|
| `project_list` | List all projects |
| `project_switch` | Switch project context |
| `project_create` | Create new project |

### Session Tools
| Tool | Description |
|------|-------------|
| `session_observe` | Add event to session |
| `session_summary` | Generate AI summary |
| `session_context` | Get session context |

### Context Tools
| Tool | Description |
|------|-------------|
| `build_context` | Build context from URIs |

## Storage Model

### Markdown as Truth
All content is stored as markdown files in Obsidian vaults. The SQLite database is a derived index that can be rebuilt from files.

### Note Structure
```markdown
---
title: Note Title
note_type: note
project: my-project
tags: [tag1, tag2]
created: 2024-01-01T00:00:00Z
updated: 2024-01-01T00:00:00Z
---

# Note Title

Content with [[wikilinks]] to other notes.

Relations can be expressed as:
- relates_to:: [[Other Note]]
- supersedes:: [[Old Note]]
```

### File Location
Notes managed by Obsidian-Memory are stored in `_claude-mem/` folder within each vault:
```
vault/
├── _claude-mem/           # Managed by Obsidian-Memory
│   ├── notes/
│   ├── sessions/
│   └── projects/
└── ... (other vault files)
```

## Environment Variables

### Backend
| Variable | Description | Default |
|----------|-------------|---------|
| `VAULT_PATH` | Path to vaults directory | `/vaults` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `REQUIRE_AUTH` | Enable Bearer auth | `false` |
| `API_TOKEN` | Bearer token | - |
| `ANTHROPIC_API_KEY` | Claude API key | - |
| `CLOUDFLARE_ACCESS_ENABLED` | Enable CF Access | `false` |
| `CLOUDFLARE_ACCESS_TEAM_DOMAIN` | CF team domain | - |

### MCP Server
| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_TRANSPORT` | `stdio` or `sse` | `stdio` |
| `MCP_SSE_PORT` | SSE server port | `3000` |
| `MCP_PATH` | MCP endpoint path | `/mcp` |
| `OBSIDIAN_MEMORY_API_URL` | Backend URL | `http://localhost:8000` |

## Security

- **Cloudflare Access**: Zero-trust authentication (recommended for production)
- **OAuth 2.1 + PKCE**: For Claude.ai MCP integration
- **Bearer Tokens**: Simple auth for development
- **Path Validation**: Prevents directory traversal
- **Non-root Containers**: Enhanced Docker security
- **Rate Limiting**: Configurable request limits

## Related Documentation

- [Cloudflare Access Setup](cloudflare-access-setup.md)
- [Secret Management](secret-management-best-practices.md)
- [Infisical Integration](infisical-integration.md)
- [MCP Implementation Audit](MCP-IMPLEMENTATION-AUDIT.md)
