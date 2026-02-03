# Architecture Documentation

Comprehensive architecture guide for Obsidian-Memory.

## Visual Diagrams

For visual learners, see our comprehensive diagram collections:

📊 **[System Architecture Diagrams](diagrams/SYSTEM-ARCHITECTURE.md)** (11 Mermaid diagrams)
- High-level system architecture
- Component interactions and data flows
- Deployment architectures
- Sequence diagrams for operations

🔐 **[OAuth Flow Diagrams](diagrams/OAUTH-FLOW.md)** (8 Mermaid diagrams)
- Authentication flows
- Token lifecycle
- Multi-client architecture
- Error handling

All diagrams render natively on GitHub and provide visual understanding of the concepts explained in this document.

## System Overview

Obsidian-Memory is a multi-tier persistent memory system designed for AI assistants. It combines:

- **Hook-based auto-capture** (cc-obsidian-mem pattern)
- **Knowledge graph navigation** (Basic Memory pattern)
- **Cross-project context library** (OpenContext pattern)
- **AI processing** for entity/relation extraction

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
│  Claude Code │ Claude.ai │ Cursor │ Web UI │ Custom Clients    │
└──────┬───────┴──────┬────┴────┬───┴────┬───┴─────────┬─────────┘
       │              │         │        │             │
       │ stdio        │ SSE     │ HTTP   │ HTTP        │ HTTP
       │              │         │        │             │
       ▼              ▼         ▼        ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Server (Bun/TypeScript)              │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Transport    │  │ Tool Handlers│  │ API Client   │        │
│  │ - Stdio      │→ │ - Memory     │→ │ - HTTP       │        │
│  │ - SSE        │  │ - Graph      │  │ - Retry      │        │
│  │ - Streamable │  │ - Project    │  │ - Auth       │        │
│  └──────────────┘  │ - Session    │  └──────────────┘        │
│                    │ - Context    │                            │
│                    └──────────────┘                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/JSON
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                     │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ Middleware  │  │ API Layer   │  │ Services    │           │
│  │ - Auth      │→ │ - Notes     │→ │ - Vault Mgr │           │
│  │ - Rate Lmt  │  │ - Graph     │  │ - Graph Eng │           │
│  │ - Validate  │  │ - Projects  │  │ - AI Proc   │           │
│  │ - CF Access │  │ - Sessions  │  │ - Search    │           │
│  │ - CORS      │  │ - Sync      │  │ - Sync      │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Storage Layer                              │
│                                                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐           │
│  │ Markdown Files       │  │ SQLite Database      │           │
│  │ (Source of Truth)    │  │ (Derived Index)      │           │
│  │                      │  │                      │           │
│  │ - Notes (md)         │  │ - notes              │           │
│  │ - Frontmatter (yaml) │  │ - graph_edges        │           │
│  │ - Wikilinks         │  │ - sessions           │           │
│  │ - Relations          │  │ - fts5_index         │           │
│  └──────────────────────┘  └──────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Client Layer

#### Claude Code (stdio)
- **Transport**: Standard I/O (stdin/stdout)
- **Use Case**: Local CLI integration
- **Features**: Hook integration for auto-capture
- **Config**: `.mcp.json` or `~/.claude.json`

#### Claude.ai (SSE)
- **Transport**: Server-Sent Events over HTTPS
- **Use Case**: Remote cloud access
- **Features**: OAuth 2.0 authentication, real-time updates
- **Config**: Claude.ai MCP settings UI

#### Cursor (Streamable HTTP)
- **Transport**: Streamable HTTP
- **Use Case**: IDE integration
- **Features**: Auto-detection, native auth flows
- **Config**: `.cursor/mcp.json`

#### Web UI (HTTP)
- **Transport**: REST API
- **Use Case**: Browser-based management
- **Stack**: Next.js, React, TypeScript

### 2. MCP Server Layer

The MCP server is the protocol adapter between clients and the backend API.

#### Transport Implementations

**Stdio Transport** (`src/transport/stdio.ts`)
- JSON-RPC 2.0 over stdio streams
- Synchronous request/response
- Used by Claude Code CLI
- No authentication required (localhost)

**SSE Transport** (`src/transport/sse.ts`)
- Server-Sent Events for server-to-client
- POST endpoint for client-to-server
- Session-based with session IDs
- OAuth 2.0 authentication support
- Unified `/mcp` endpoint:
  - `POST /mcp` - JSON-RPC requests
  - `GET /mcp` - SSE stream
  - `DELETE /mcp` - Close session

**Streamable HTTP** (auto-detected by Cursor)
- HTTP-based bidirectional streaming
- Native Cursor integration
- OAuth support via `auth` block in config

#### Tool Categories

**Memory Tools** (`src/tools/memory.ts`)
- `mem_read`: Read notes by ID/permalink/search
- `mem_write`: Create/update notes with frontmatter
- `mem_search`: FTS5 search with filters
- `mem_supersede`: Mark notes as superseded

**Graph Tools** (`src/tools/graph.ts`)
- `graph_traverse`: BFS/DFS graph traversal
- `graph_similar`: Similarity search (graph/content/hybrid)

**Project Tools** (`src/tools/project.ts`)
- `project_list`: List projects with counts
- `project_switch`: Context switching
- `project_create`: Create with validation

**Session Tools** (`src/tools/session.ts`)
- `session_observe`: Add events
- `session_summary`: AI summarization
- `session_context`: Get context with history

**Context Tools** (`src/tools/context.ts`)
- `build_context`: Build from memory:// URIs

#### API Client

The MCP server includes a robust HTTP client:
- Automatic retry with exponential backoff
- Bearer token authentication
- Request/response logging
- Error handling and transformation

### 3. Backend Layer (FastAPI)

#### Middleware Chain

Request flow through middleware (ordered):

1. **Validation Middleware** (`middleware/validation.py`)
   - Path traversal protection
   - Content-Type validation
   - Request size limits
   - Runs first for security

2. **Rate Limiting** (`middleware/rate_limit.py`)
   - Token bucket algorithm
   - Per-IP tracking
   - Configurable limits
   - Response headers

3. **Cloudflare Access** (`middleware/cloudflare_access.py`)
   - JWT validation
   - Public key caching
   - Team domain verification
   - Skip paths for OAuth endpoints

4. **Authentication** (`middleware/auth.py`)
   - Bearer token validation
   - Skip paths for public endpoints
   - OAuth endpoint exemptions

5. **CORS** (FastAPI built-in)
   - Configurable origins
   - Credentials support
   - Exposed headers

#### API Structure

**RESTful Endpoints** (`app/api/`)
- `notes.py` - CRUD operations for notes
- `graph.py` - Knowledge graph queries
- `projects.py` - Project management
- `sessions.py` - Session tracking
- `vaults.py` - Vault registration
- `sync.py` - Git synchronization
- `ai.py` - AI processing endpoints
- `mcp.py` - MCP proxy endpoints

**MCP Proxy Endpoints** (`app/api/mcp.py`)
The backend proxies MCP requests to the MCP server container:
- `POST /mcp` - Forward JSON-RPC to MCP server
- `GET /mcp/sse` - Proxy SSE stream
- OAuth discovery endpoints (`.well-known/*`)

#### Services Layer

**VaultService** (`services/vault_service.py`)
- Vault registration and management
- File I/O with atomic writes
- Path validation and sanitization
- Multi-vault support

**GraphService** (`services/graph_service.py`)
- Graph construction from wikilinks
- Relation extraction from frontmatter
- BFS/DFS traversal algorithms
- Similarity computation

**AIService** (`services/ai_service.py`)
- Claude API integration
- Entity extraction from text
- Relation inference
- Session summarization
- Token usage tracking

**SearchService** (`services/search_service.py`)
- SQLite FTS5 full-text search
- Index management
- Ranking and relevance
- Filter support (tags, project, type)

**SyncService** (`services/sync_service.py`)
- Git repository operations
- Conflict detection and resolution
- Device tracking
- Auto-commit with device metadata

### 4. Storage Layer

#### Markdown Files (Source of Truth)

All data is stored as markdown files in Obsidian vaults:

```
vault/
├── _claude-mem/              # Managed by Obsidian-Memory
│   ├── notes/
│   │   ├── note-1.md
│   │   └── note-2.md
│   ├── sessions/
│   │   └── session-abc123.md
│   └── projects/
│       └── project-xyz.md
└── ... (other vault files)
```

**Note Format**:
```markdown
---
title: Example Note
permalink: example-note
note_type: note
project: my-project
tags: [tag1, tag2]
created: 2024-01-01T00:00:00Z
updated: 2024-01-01T00:00:00Z
relates_to: [[related-note]]
superseded_by: [[newer-note]]
---

# Example Note

Content with [[wikilinks]] and plain text.

Relations can be expressed in frontmatter or inline:
- relates_to:: [[Another Note]]
```

#### SQLite Database (Derived Index)

The database is a performance optimization - it can be rebuilt from files:

**Schema**:
- `notes` - Note metadata and content
- `graph_edges` - Wikilink relationships
- `sessions` - Session tracking
- `session_events` - Event log
- `fts5_notes` - Full-text search index

**Indexing Strategy**:
- Note content indexed in FTS5 virtual table
- Graph edges indexed for traversal performance
- Session events indexed by timestamp
- All indexes can be rebuilt from markdown

## Data Flow Examples

### Write Operation

```
1. Client calls mem_write via MCP
2. MCP server sends POST /api/notes to backend
3. Backend validates request (middleware chain)
4. VaultService writes to markdown file (atomic write)
5. Database updated from markdown (derived index)
6. Graph edges extracted and indexed
7. FTS5 index updated
8. Response sent back through MCP to client
```

### Read Operation

```
1. Client calls mem_read via MCP
2. MCP server sends GET /api/notes/{id} to backend
3. Backend checks database for metadata
4. VaultService reads markdown file
5. Content parsed and formatted
6. Response sent back through MCP to client
```

### Search Operation

```
1. Client calls mem_search via MCP
2. MCP server sends POST /api/notes/search to backend
3. SearchService queries FTS5 index
4. Results filtered by tags/project/type
5. Notes loaded from database (or files if needed)
6. Results ranked by relevance
7. Response sent back through MCP to client
```

### Graph Traversal

```
1. Client calls graph_traverse via MCP
2. MCP server sends GET /api/graph/traverse to backend
3. GraphService performs BFS/DFS on graph_edges
4. Note metadata loaded for visited nodes
5. Traversal results assembled
6. Response sent back through MCP to client
```

## Security Architecture

### Authentication Layers

1. **Network Layer**: Cloudflare Tunnel + Access
   - Zero Trust network access
   - OAuth 2.0 authentication
   - JWT validation

2. **Application Layer**: FastAPI middleware
   - Bearer token validation
   - Cloudflare Access JWT verification
   - OAuth 2.1 + PKCE support

3. **Transport Layer**: MCP server
   - No auth required for stdio (localhost only)
   - OAuth support for SSE transport

### Security Features

- **Path Traversal Protection**: Validates all file paths
- **Rate Limiting**: Token bucket per IP
- **Request Validation**: Size limits, content-type checks
- **Atomic Writes**: Prevents partial file writes
- **Non-root Containers**: Enhanced Docker security
- **Secret Management**: Environment variables only, no hardcoded secrets

## Deployment Architecture

### Development

```
Host Machine
├── Backend: localhost:8765
├── MCP Server: localhost:3000
└── Web UI: localhost:3001
```

### Production (Docker)

```
Internet
    ↓
Cloudflare Tunnel (cloudflared)
    ↓
Traefik Reverse Proxy
    ↓
Docker Network (proxy)
    ├── memory (backend)
    ├── memory-mcp (MCP server)
    └── memory-web (Web UI)
```

### High Availability Setup

For production, consider:
- Multiple backend replicas behind load balancer
- Shared vault storage (NFS/S3)
- Database replication (SQLite → PostgreSQL for multi-instance)
- Redis for session state (if horizontal scaling needed)

## Performance Considerations

### Indexing
- FTS5 index updated incrementally on writes
- Graph edges computed on note save
- Background reindexing available via API

### Caching
- Cloudflare Access public keys cached (1 hour TTL)
- Graph traversal results not cached (dynamic)
- Note reads served from database (fast)

### Scaling
- Backend: Stateless, horizontally scalable
- MCP Server: Stateless, horizontally scalable
- Storage: Shared filesystem or object storage required for multi-instance
- Database: SQLite sufficient for single instance, PostgreSQL for multi-instance

## Extension Points

### Custom Tools
Add new MCP tools in `mcp-server/src/tools/`:
```typescript
export const myCustomTool: McpTool = {
  name: "my_custom_tool",
  description: "Does something custom",
  inputSchema: { ... },
  handler: async (args) => { ... }
};
```

### Custom Middleware
Add middleware in `backend/app/middleware/`:
```python
async def my_middleware(request: Request, call_next):
    # Pre-processing
    response = await call_next(request)
    # Post-processing
    return response
```

### Custom Services
Extend services in `backend/app/services/`:
```python
class MyCustomService:
    def __init__(self, vault_service: VaultService):
        self.vault_service = vault_service

    async def do_something(self):
        # Custom logic
        pass
```

## Monitoring and Observability

### Health Endpoints
- `GET /health` - Basic health check
- `GET /metrics` - System metrics (CPU, memory, threads)

### Logging
- Structured JSON logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Automatic log rotation (10MB, 5 backups)
- Log files: `~/.obsidian-memory/logs/obsidian-memory.log`

### Metrics
- Request count
- Response times
- Error rates
- Rate limit violations
- AI API usage

## Development Workflow

### Local Development
1. Start backend: `uvicorn app.main:app --reload`
2. Start MCP server: `bun run dev`
3. Start Web UI: `npm run dev`
4. Test with Claude Code or Cursor

### Testing
- Backend: `pytest` (unit + integration)
- MCP Server: `bun test` (unit + E2E)
- Web UI: `npm test` (Jest + React Testing Library)

### CI/CD
- GitHub Actions for tests
- Docker image builds on push
- Automatic deployment to production (ghcr.io registry)

## References

- [API Documentation](api.md)
- [MCP Server README](../mcp-server/README.md)
- [Deployment Guide](deployment.md)
- [Authentication Guide](AUTHENTICATION.md)
