# Obsidian-Memory Implementation Plan

## Status Legend
- [ ] Not started
- [~] In progress
- [x] Complete

## Phase 1: Core Foundation

### Priority: Critical
- [x] **S** Backend project scaffolding (pyproject.toml, structure)
- [x] **S** MCP server scaffolding (package.json, tsconfig)
- [x] **S** Web UI scaffolding (Next.js setup)
- [x] **M** Vault manager service (read/write markdown files)
- [x] **M** Markdown parser (frontmatter, observations, relations)
- [x] **M** SQLite + FTS5 search index
- [x] **M** Basic CRUD API endpoints (/api/notes/*)
- [x] **L** MCP tools: mem_read, mem_write, mem_search

## Phase 2: Knowledge Graph

### Priority: High
- [x] **M** Graph engine (compute nodes/edges from markdown)
- [ ] **M** Wikilink extraction and resolution
- [ ] **M** Relation parsing from markdown
- [ ] **M** Graph traversal queries
- [ ] **L** build_context tool (memory:// URI patterns)
- [ ] **M** MCP tools: graph_traverse, graph_similar

## Phase 3: AI Processing

### Priority: High
- [ ] **M** AI processor service (Claude API)
- [ ] **L** Entity extraction from content
- [ ] **L** Automatic relation inference
- [ ] **M** Session summarization
- [ ] **L** Pattern detection

## Phase 4-8: See specs/ for details

---

## Discoveries

<!-- Findings during implementation -->

## Blockers

<!-- Current blockers -->
