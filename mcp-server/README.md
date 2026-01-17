# Obsidian-Memory MCP Server

MCP (Model Context Protocol) server for Obsidian-Memory, providing memory management tools for Claude Code.

## Features

- **Memory Tools**: Read, write, and search notes
- **Graph Tools**: Traverse knowledge graph and find similar notes
- **Project Tools**: Manage projects and switch contexts
- **Session Tools**: Track sessions, observe events, and generate summaries
- **Context Building**: Build context from memory:// URIs

## Installation

```bash
bun install
```

## Usage

### Stdio Transport (Default - for Claude Code CLI)

```bash
bun run src/index.ts
```

Or set explicitly:
```bash
MCP_TRANSPORT=stdio bun run src/index.ts
```

### SSE Transport (for Claude.ai / Remote Access)

Start the server with SSE transport:

```bash
MCP_TRANSPORT=sse MCP_SSE_PORT=3000 bun run src/index.ts
```

The server will:
- Listen on `http://localhost:3000/sse` for SSE connections
- Accept messages at `http://localhost:3000/message`

### Environment Variables

- `MCP_TRANSPORT` - Transport type: `stdio` (default) or `sse`
- `MCP_SSE_PORT` - Port for SSE server (default: 3000)
- `MCP_SSE_PATH` - Path for SSE endpoint (default: `/sse`)
- `OBSIDIAN_MEMORY_API_URL` - Backend API URL (default: `http://localhost:8000`)

## Development

```bash
# Run in development mode with watch
bun run dev

# Type check
bun run typecheck

# Lint
bun run lint

# Format
bun run format

# Test
bun test
```

## Building

```bash
bun run build
```

## Tools

The server provides the following MCP tools:

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
