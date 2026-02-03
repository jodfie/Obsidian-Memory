# AI Model Quick Reference

Fast reference guide for AI models using Obsidian-Memory.

## System Architecture (10-Second Overview)

```
Clients (Claude.ai/Code/Cursor)
    ↓ MCP Protocol
MCP Server (TypeScript)
    ↓ HTTP/JSON
Backend API (Python/FastAPI)
    ↓
Storage (Markdown + SQLite)
```

**Transport Types**:
- **stdio**: Local CLI (Claude Code) - no auth
- **SSE**: Remote HTTPS (Claude.ai) - OAuth 2.0
- **Streamable HTTP**: IDE (Cursor) - auto-detected

## Connection Endpoints

| Client | URL | Auth |
|--------|-----|------|
| Claude.ai | `https://memory.redleif.dev/mcp` | OAuth 2.0 |
| Cursor | `https://memory.redleif.dev/mcp` | OAuth (optional) |
| Claude Code | stdio (local process) | None |
| Web UI | `https://memory.redleif.dev` | Cloudflare Access |

## OAuth Credentials (Claude.ai)

```
Server URL: https://memory.redleif.dev/mcp
Client ID: 996ac4873739812cad6edd18fbd572b150b5e0bea38fa30299b8e3f393fb6a22
Client Secret: pkce_no_secret_required
Authorization URL: https://redleif.cloudflareaccess.com/cdn-cgi/access/authorize
Token URL: https://redleif.cloudflareaccess.com/cdn-cgi/access/token
```

## MCP Tools (13 Total)

### Memory (4 tools)
| Tool | Purpose | Key Args |
|------|---------|----------|
| `mem_read` | Get note content | `id` or `permalink` |
| `mem_write` | Create/update note | `title`, `content`, `tags` |
| `mem_search` | Full-text search | `query`, filters |
| `mem_supersede` | Mark as outdated | `old_note_id`, `new_note_id` |

### Graph (2 tools)
| Tool | Purpose | Key Args |
|------|---------|----------|
| `graph_traverse` | Navigate links | `start_note_id`, `max_depth` |
| `graph_similar` | Find related | `note_id`, `method` |

### Project (3 tools)
| Tool | Purpose | Key Args |
|------|---------|----------|
| `project_list` | List projects | - |
| `project_switch` | Change context | `project_name` |
| `project_create` | New project | `project_name` |

### Session (3 tools)
| Tool | Purpose | Key Args |
|------|---------|----------|
| `session_observe` | Log event | `event_type`, `content` |
| `session_summary` | AI summary | `session_id` |
| `session_context` | Get history | `session_id` |

### Context (1 tool)
| Tool | Purpose | Key Args |
|------|---------|----------|
| `build_context` | Load URIs | `memory_uris` |

## Common Workflows

### Initialize Memory
```
1. Search existing: mem_search query="topic"
2. If none, create: mem_write title="Topic" content="..."
3. Link related: Use [[wikilinks]] in content
```

### Load Context
```
1. Search: mem_search query="relevant terms"
2. Read specifics: mem_read permalink="key-note"
3. Explore: graph_traverse start_note_id=X
```

### Save Knowledge
```
1. Write note: mem_write with tags
2. Link: Include [[wikilinks]] to related notes
3. Track: session_observe to log the creation
```

### Find Related
```
1. Direct links: graph_traverse from starting note
2. Content similarity: graph_similar method="content"
3. Hybrid: graph_similar method="hybrid"
```

## Note Structure

### Markdown Format
```markdown
---
title: Note Title
permalink: note-title
note_type: note
project: my-project
tags: [tag1, tag2]
created: 2024-01-01T00:00:00Z
updated: 2024-01-01T00:00:00Z
relates_to: [[related-note]]
superseded_by: [[newer-version]]
---

# Note Title

Content with [[wikilinks]] to create graph edges.

Inline relations:
- relates_to:: [[Another Note]]
- inspired_by:: [[Source]]
```

### Note Types
- `note` - General knowledge
- `session` - Conversation record
- `project` - Project metadata
- `entity` - Extracted entity
- `relation` - Relationship definition

## Storage Location

Notes are stored in: `vault/_claude-mem/`

```
vault/
├── _claude-mem/           # Managed by Obsidian-Memory
│   ├── notes/            # General notes
│   ├── sessions/         # Session records
│   └── projects/         # Project metadata
└── ... (other files)     # User's own files
```

## Search Capabilities

### Full-Text Search (FTS5)
```
mem_search query="python async patterns"
```

### Filter by Tags
```
mem_search query="*" tags=["python", "async"]
```

### Filter by Project
```
mem_search query="api" project="backend"
```

### Filter by Type
```
mem_search query="*" note_type="session"
```

### Combined Filters
```
mem_search query="error handling"
           project="backend"
           tags=["python"]
           note_type="note"
```

## Graph Algorithms

### BFS (Breadth-First)
Explores all neighbors before going deeper:
```
graph_traverse start_note_id=1 algorithm="bfs" max_depth=2
```
**Use for**: Finding all nearby connections

### DFS (Depth-First)
Follows each path to maximum depth:
```
graph_traverse start_note_id=1 algorithm="dfs" max_depth=3
```
**Use for**: Following specific threads of thought

### Similarity Methods

**Graph-based**: Shared connections
```
graph_similar note_id=1 method="graph" limit=10
```

**Content-based**: Text similarity
```
graph_similar note_id=1 method="content" limit=10
```

**Hybrid**: Both combined
```
graph_similar note_id=1 method="hybrid" limit=10
```

## Response Formats

All tools support two formats:

### JSON (default)
```
mem_read id=1 response_format="json"
```
Returns structured data for programmatic use.

### Markdown
```
mem_read id=1 response_format="markdown"
```
Returns human-readable formatted text.

## Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 400 | Bad request | Check parameters |
| 401 | Unauthorized | Reconnect/re-auth |
| 403 | Forbidden | Check access policy |
| 404 | Not found | Verify ID/permalink |
| 409 | Conflict | Different vaults or circular reference |
| 429 | Rate limited | Wait and retry |
| 500 | Server error | Check logs |
| 503 | Service down | Check backend/AI API |

## Performance Tips

### Efficient Searches
- Use specific queries over `*` wildcard
- Add filters to narrow results
- Use reasonable limits (default: 50)

### Graph Operations
- Limit traversal depth (max_depth=2-3)
- Use BFS for breadth, DFS for depth
- Cache results when possible

### Batch Operations
- Group related writes
- Use wikilinks to batch-create relationships
- Leverage session tracking for context

## Authentication Quick Debug

### Claude.ai Connection Issues
1. Check server health: `curl https://memory.redleif.dev/mcp/health`
2. Verify OAuth credentials match exactly
3. Disconnect and reconnect to refresh token
4. Check email is in Cloudflare Access policy

### Cursor Connection Issues
1. Use native auth flow: Settings → MCP → Login
2. Or add static OAuth to `.cursor/mcp.json`
3. Test server: `curl https://memory.redleif.dev/health`

### Claude Code Connection Issues
1. Verify MCP config in `~/.claude.json` or `.mcp.json`
2. Check backend is running: `curl http://localhost:8765/health`
3. Test MCP server: `bun run src/index.ts` (should not error)

## Environment Variables Reference

### Backend
```bash
VAULT_PATH=/vaults              # Where vaults are stored
ANTHROPIC_API_KEY=sk-...        # For AI features
CLOUDFLARE_ACCESS_ENABLED=true  # Enable CF Access
REQUIRE_AUTH=false              # Bearer token auth
```

### MCP Server
```bash
MCP_TRANSPORT=sse               # stdio or sse
MCP_SSE_PORT=3000              # SSE server port
OBSIDIAN_MEMORY_API_URL=http://localhost:8765
```

## API Endpoints (Direct Access)

If bypassing MCP:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/api/notes` | GET | List notes |
| `/api/notes` | POST | Create note |
| `/api/notes/{id}` | GET | Get note |
| `/api/notes/{id}` | PUT | Update note |
| `/api/notes/search` | POST | Search notes |
| `/api/graph` | GET | Full graph |
| `/api/projects` | GET | List projects |
| `/api/sessions` | GET | List sessions |

## Docker Containers

| Container | Port | Purpose |
|-----------|------|---------|
| `memory` | 8765 | Backend API |
| `memory-mcp` | 3000 | MCP server |
| `memory-web` | 3001 | Web UI |
| `cloudflared` | - | CF Tunnel |

## Quick Diagnostic Commands

```bash
# Check all services
docker ps | grep memory

# Health checks
curl http://localhost:8765/health
curl http://localhost:3000/health

# View logs
docker logs memory
docker logs memory-mcp

# Test MCP endpoint
curl https://memory.redleif.dev/mcp/health

# Check vault permissions
docker exec memory ls -la /vaults
```

## Related Documentation

| Doc | Purpose |
|-----|---------|
| [Quick Start](QUICK-START.md) | 5-minute setup |
| [Architecture](ARCHITECTURE.md) | Deep dive |
| [Claude.ai Integration](CLAUDE-AI-INTEGRATION.md) | Detailed Claude.ai setup |
| [API Reference](api.md) | Complete API docs |
| [Troubleshooting](TROUBLESHOOTING.md) | Problem solving |

## Support Resources

- **GitHub**: https://github.com/jodfie/Obsidian-Memory
- **Issues**: https://github.com/jodfie/Obsidian-Memory/issues
- **Docs**: https://github.com/jodfie/Obsidian-Memory/tree/main/docs
