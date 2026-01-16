# Obsidian-Memory Product Requirements Document

## Executive Summary

Obsidian-Memory is a unified memory management system for Claude Code that combines hook-based auto-capture, knowledge graph navigation, cross-project context sharing, and heavy AI processing. It stores all knowledge in human-readable Markdown files compatible with Obsidian while providing fast search and graph queries through computed indexes.

## Problem Statement

Current AI coding assistants lose context between sessions, requiring users to repeatedly explain project details, past decisions, and learned patterns. Existing solutions are fragmented:

- **cc-obsidian-mem**: Good auto-capture but no knowledge graph
- **Basic Memory**: Good graph/relations but no auto-capture
- **OpenContext**: Good cross-project sharing but limited AI integration

Users need a unified system that automatically captures knowledge, builds semantic relationships, and provides intelligent retrieval across all their projects.

## Target Users

1. **Power Claude Code users** who work across multiple projects
2. **Developers** who want persistent AI memory without vendor lock-in
3. **Teams** who need shared knowledge bases accessible via web UI

## Core Principles

1. **Markdown is Truth** - All knowledge stored as human-readable, editable Markdown
2. **Computed Indexes** - Graph and search indexes derived from Markdown, always regenerable
3. **Multi-Vault Federation** - Unified view across multiple Obsidian vaults
4. **Universal Access** - MCP (Claude), REST API (any client), Web UI (browser)
5. **Heavy AI Processing** - Automatic entity extraction, relation inference, summarization

---

## Functional Requirements

### FR-1: Vault Management

**FR-1.1**: Support multiple Obsidian vaults with independent configuration
**FR-1.2**: Atomic file writes to prevent corruption
**FR-1.3**: Path traversal protection for security
**FR-1.4**: Read-only vault mode for shared/reference vaults
**FR-1.5**: Memory folder structure (`_claude-mem/`) for AI-generated notes

### FR-2: Markdown Parsing

**FR-2.1**: Parse YAML frontmatter with standard fields (title, type, project, tags, etc.)
**FR-2.2**: Extract structured observations: `- [category] content #tags (context)`
**FR-2.3**: Extract semantic relations: `- relation_type [[Target]]`
**FR-2.4**: Extract and resolve wikilinks: `[[Note]]`, `[[Note|Display]]`, `[[path/Note]]`
**FR-2.5**: Preserve original content structure on round-trip serialization

### FR-3: Search Index

**FR-3.1**: Full-text search using SQLite FTS5 with porter stemmer
**FR-3.2**: Boolean operators (AND, OR, NOT) and phrase search
**FR-3.3**: Filter by vault, project, type, tags, date range
**FR-3.4**: Relevance-ranked results with highlighted snippets
**FR-3.5**: Incremental indexing with change detection (file hash)

### FR-4: Knowledge Graph

**FR-4.1**: Compute graph nodes from notes (Note, Entity, Pattern, Session)
**FR-4.2**: Compute graph edges from wikilinks and explicit relations
**FR-4.3**: Graph traversal queries (neighbors, paths, subgraphs)
**FR-4.4**: Semantic similarity search (find related notes)
**FR-4.5**: Backlink queries (what links to this note)
**FR-4.6**: `build_context` tool for memory:// URI patterns

### FR-5: AI Processing

**FR-5.1**: Entity extraction from note content (people, tools, concepts, errors)
**FR-5.2**: Automatic relation inference between notes
**FR-5.3**: Session summarization (compress session logs to key learnings)
**FR-5.4**: Pattern detection across notes (recurring solutions, techniques)
**FR-5.5**: Knowledge deduplication suggestions

### FR-6: MCP Server

**FR-6.1**: Memory tools: `mem_read`, `mem_write`, `mem_search`, `mem_supersede`
**FR-6.2**: Graph tools: `graph_traverse`, `graph_similar`, `graph_context`
**FR-6.3**: Project tools: `project_list`, `project_switch`, `project_create`
**FR-6.4**: Session tools: `session_observe`, `session_summary`, `session_context`
**FR-6.5**: Support stdio transport (Claude Code CLI)
**FR-6.6**: Support SSE transport (Claude.ai, remote access)

### FR-7: Claude Code Hooks

**FR-7.1**: SessionStart - Load project context, inject recent memories
**FR-7.2**: UserPromptSubmit - Log user intent for session tracking
**FR-7.3**: PostToolUse - Capture file edits, commands, errors, web research
**FR-7.4**: PreCompact - Trigger AI summarization before context loss
**FR-7.5**: SessionEnd - Finalize session, extract patterns, sync

### FR-8: REST API

**FR-8.1**: CRUD endpoints for notes (`/api/notes/*`)
**FR-8.2**: Graph query endpoints (`/api/graph/*`)
**FR-8.3**: Search endpoint (`/api/search`)
**FR-8.4**: Project management endpoints (`/api/projects/*`)
**FR-8.5**: Session endpoints (`/api/sessions/*`)
**FR-8.6**: Sync endpoints (`/api/sync/*`)
**FR-8.7**: Authentication via Cloudflare Access or Bearer tokens

### FR-9: Web UI

**FR-9.1**: Dashboard with recent activity, stats, quick search
**FR-9.2**: Notes browser with filtering and sorting
**FR-9.3**: Markdown editor with live preview (split view)
**FR-9.4**: Interactive knowledge graph visualization
**FR-9.5**: Project management interface
**FR-9.6**: Session history and timeline view
**FR-9.7**: Settings and configuration UI

### FR-10: Multi-Project Support

**FR-10.1**: Project-scoped notes within vaults
**FR-10.2**: Global patterns shared across projects
**FR-10.3**: Cross-project search and graph queries
**FR-10.4**: Context library for reusable knowledge (OpenContext style)
**FR-10.5**: Project switching in MCP and UI

---

## Non-Functional Requirements

### NFR-1: Performance

- Search queries return in <100ms for 10k notes
- Graph traversal completes in <200ms for depth-3 queries
- Incremental indexing processes 100 notes/second
- Web UI loads in <2 seconds

### NFR-2: Scalability

- Support up to 50,000 notes across all vaults
- Support up to 10 concurrent MCP connections
- Support up to 100 concurrent API requests

### NFR-3: Reliability

- Atomic writes prevent data corruption
- Graceful degradation if AI services unavailable
- Automatic index recovery from Markdown source

### NFR-4: Security

- Path traversal protection on all file operations
- Authentication required for remote access
- No secrets stored in Markdown files
- Sandboxed execution for hooks

### NFR-5: Compatibility

- Obsidian-compatible Markdown format
- Standard MCP protocol compliance
- Works with Claude Code CLI and Claude.ai
- Cross-platform (Linux, macOS, Windows via Docker)

---

## Technical Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│  Claude Code (Hooks)  │  Claude.ai (MCP)  │  Web UI (Next.js)  │
└───────────┬───────────┴─────────┬─────────┴─────────┬──────────┘
            │                     │                   │
            ▼                     ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP SERVER (TypeScript/Bun)                 │
│  Tools: mem_*, graph_*, project_*, session_*                    │
│  Transports: stdio, SSE                                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BACKEND (Python/FastAPI)                      │
├─────────────────────────────────────────────────────────────────┤
│  VaultManager  │  MarkdownParser  │  SearchIndex  │  GraphEngine│
│  AIProcessor   │  SessionTracker  │  SyncService                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STORAGE LAYER                              │
├─────────────────────────────────────────────────────────────────┤
│  Markdown Files (Source of Truth)  │  SQLite + FTS5 (Index)    │
│  Multiple Obsidian Vaults          │  Computed Graph Cache      │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, Pydantic, aiosqlite |
| MCP Server | TypeScript, Bun, @modelcontextprotocol/sdk |
| Web UI | Next.js 14, React 18, Tailwind CSS |
| Database | SQLite with FTS5 extension |
| AI | Anthropic Claude API |
| Auth | Cloudflare Access / Bearer tokens |
| Deployment | Docker, Docker Compose, Traefik |

### Data Flow

1. **Write Path**: Client → MCP/API → VaultManager → Markdown File → SearchIndex
2. **Read Path**: Client → MCP/API → SearchIndex/Graph → VaultManager → Markdown File
3. **AI Path**: Content → AIProcessor → Extracted Entities/Relations → SearchIndex

---

## Implementation Phases

### Phase 1: Core Foundation
- Vault Manager (multi-vault file I/O)
- Markdown Parser (frontmatter, observations, relations)
- Search Index (SQLite FTS5)
- Basic API endpoints

### Phase 2: Knowledge Graph
- Graph engine (compute from Markdown)
- Graph traversal and queries
- build_context tool
- Backlinks and similarity

### Phase 3: AI Processing
- Entity extraction
- Relation inference
- Session summarization
- Pattern detection

### Phase 4: MCP Server
- Memory tools (mem_*)
- Graph tools (graph_*)
- Project tools (project_*)
- Session tools (session_*)
- stdio and SSE transports

### Phase 5: Claude Code Hooks
- SessionStart, PostToolUse, SessionEnd
- Observation capture
- Context injection
- Auto-summarization

### Phase 6: Web UI
- Dashboard and notes browser
- Markdown editor
- Graph visualization
- Project management

### Phase 7: Sync & Auth
- Git sync service
- Conflict resolution
- Cloudflare Access integration
- Cross-device sync

### Phase 8: Production
- Docker optimization
- Monitoring and logging
- Documentation
- Performance tuning

---

## Success Metrics

1. **Adoption**: Used daily for 30+ days without context re-explanation
2. **Performance**: Search/graph queries consistently <200ms
3. **Reliability**: Zero data loss incidents
4. **Coverage**: Auto-captures 80%+ of session learnings

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| AI costs for heavy processing | Batch processing, caching, configurable triggers |
| Index corruption | Regenerable from Markdown source |
| Breaking Obsidian compatibility | Extensive format testing, preserve unknown fields |
| Performance at scale | Incremental indexing, query optimization |

---

## Open Questions

1. Should canvas visualization be a priority feature?
2. What's the maximum reasonable vault size to support?
3. Should we support real-time collaboration in web UI?
4. Integration with other note-taking apps beyond Obsidian?

---

## Appendix

### Related Specifications

- `specs/core-vault-manager.md` - Vault file operations
- `specs/core-markdown-parser.md` - Markdown parsing
- `specs/core-search-index.md` - Search indexing
- Additional specs to be created for each phase

### References

- [cc-obsidian-mem](https://github.com/z-m-huang/cc-obsidian-mem)
- [Basic Memory](https://github.com/basicmachines-co/basic-memory)
- [OpenContext](https://github.com/0xranx/OpenContext)
- [Ralph Wiggum Technique](https://github.com/ghuntley/how-to-ralph-wiggum)
