# Agent Integration Guide

How to integrate Obsidian-Memory into OpenClaw agent workflows.

## SOUL.md Integration

Add to your agent's `SOUL.md` to enable memory-aware behavior:

```markdown
## Memory System

Enhanced Obsidian-Memory = PRIMARY MEMORY SYSTEM

### Memory-First Protocol
1. **ALWAYS mem_search FIRST** before answering questions about past work, decisions, or patterns
2. **mem_write with tags and wikilinks** when recording decisions, patterns, or knowledge
3. **graph_traverse** to discover connected knowledge
4. **session_observe** to log significant events during work

### Memory Workflow
- Start sessions with `recall` to load relevant context
- Search before creating — avoid duplicate notes
- Tag consistently: use project tags, type tags, and topic tags
- Link related notes with [[wikilinks]] in content
- End sessions with `session_summary` to capture learnings

### Note Conventions
- Titles: descriptive, searchable (e.g., "PostgreSQL Connection Pooling Pattern")
- Note types: decision, error, knowledge, pattern, session, research
- Tags: lowercase, hyphenated (e.g., "api-design", "docker", "auth")
- Wikilinks: reference related notes inline (e.g., "See [[Redis Caching Pattern]]")
```

## TOOLS.md Integration

Add environment-specific configuration to your agent's `TOOLS.md`:

```markdown
## Obsidian-Memory Configuration

API_URL: https://memory.example.com/api
API_KEY: (stored in secrets)

### Available Scripts
- search.sh — Search knowledge base
- write_note.sh — Record decisions and knowledge
- read_note.sh — Retrieve specific notes
- session_log.sh — Log session events
- recall.sh — Quick memory recall
- build_context.sh — Build context from memory:// URIs
```

## Hook Integration

### Before Agent Start — Load Context

Create a hook that loads relevant context before the agent begins work:

```bash
#!/usr/bin/env bash
# hooks/before_agent_start.sh
source "$(dirname "$0")/../skills/obsidian-memory-openclaw/scripts/_lib.sh"

PROJECT="${AGENT_PROJECT:-}"
if [ -n "$PROJECT" ]; then
    echo "Loading memory context for project: $PROJECT"
    mem_search "$PROJECT" 5 | jq -r '.results[]? | "- \(.title): \(.snippet // "")"'
fi
```

### After Agent Complete — Save Session

```bash
#!/usr/bin/env bash
# hooks/after_agent_complete.sh
source "$(dirname "$0")/../skills/obsidian-memory-openclaw/scripts/_lib.sh"

SESSION_ID="${AGENT_SESSION_ID:-}"
if [ -n "$SESSION_ID" ]; then
    echo "Saving session summary..."
    mem_post "sessions/${SESSION_ID}/summary" '{}' | jq -r '.summary // "No summary generated"'
fi
```

## MCP vs REST Approach

OpenClaw agents can use Obsidian-Memory in two ways:

### 1. MCP Tools (if MCP is configured)
If the agent has MCP access, use the 16 MCP tools directly (mem_read, mem_write, mem_search, etc.). This is the preferred approach for agents that support MCP.

### 2. REST Scripts (fallback)
Use the scripts in `scripts/` to call the REST API directly. This works in any environment with `curl` and `jq`.

## Best Practices for Agents

### Search Before Writing
Always search for existing notes before creating new ones. This prevents duplicates and encourages linking to existing knowledge.

### Use Consistent Tags
Maintain a taxonomy of tags across the knowledge base:
- **Project tags**: `project-name` (matches project field)
- **Type tags**: `api`, `database`, `security`, `deployment`, `testing`
- **Action tags**: `todo`, `blocked`, `resolved`, `deprecated`

### Session Tracking
Create a session at the start of each agent run. Log significant events:
- `decision` — architectural or technical choices
- `error` — problems encountered
- `solution` — how problems were resolved
- `observation` — notable findings during work

### Graph Awareness
Use `[[wikilinks]]` in note content to build the knowledge graph organically. When a note references a concept that has its own note, link to it. This enables graph traversal and similarity discovery later.

### Memory Hygiene
- Use `mem_supersede` when updating outdated information (keeps audit trail)
- Set appropriate `note_type` for easy filtering
- Add `project` field to scope notes to their context
- Review and clean up notes periodically
