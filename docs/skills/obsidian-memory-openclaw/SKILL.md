---
name: obsidian-memory-openclaw
description: Full Obsidian-Memory integration for OpenClaw agents. Provides bash scripts for REST API access, agent integration patterns for SOUL.md, session tracking, knowledge graph traversal, and memory-first workflows. Includes hook templates and best practices for agent memory management.
---

# Obsidian-Memory for OpenClaw

Complete integration skill for using **Obsidian-Memory** in **OpenClaw/Clawdbot** agent workflows. Provides REST API scripts, agent integration patterns, and memory-first workflow guidance.

## Prerequisites

- `curl` and `jq` installed
- Obsidian-Memory backend running
- Environment variables set:

```bash
export OBSIDIAN_MEMORY_API_URL="https://memory.example.com/api"
export OBSIDIAN_MEMORY_API_KEY="your-api-key"  # if auth enabled
```

## Scripts

### `scripts/search.sh` — Search Notes

```bash
./scripts/search.sh "authentication patterns" 10 "TechKB" "pattern"
```

### `scripts/read_note.sh` — Read a Note

```bash
./scripts/read_note.sh 42              # by ID
./scripts/read_note.sh "redis caching"  # by search
```

### `scripts/write_note.sh` — Create a Note

```bash
./scripts/write_note.sh "API Auth Pattern" "## JWT Flow\n..." "patterns/auth.md" "pattern" "api" "auth,jwt"
```

### `scripts/session_log.sh` — Log Session Event

```bash
./scripts/session_log.sh "agent-session-001" "decision" "Chose REST over GraphQL"
```

Event types: `observation` | `decision` | `error` | `solution` | `tool_use` | `file_edit` | `command` | `research` | `user_prompt`

### `scripts/recall.sh` — Quick Recall

```bash
./scripts/recall.sh "deployment" "TechKB"
```

### `scripts/build_context.sh` — Build Context from URIs

```bash
./scripts/build_context.sh "memory://search/auth" "memory://project/api" "memory://tags/security"
```

Supported URI patterns:
- `memory://note/123` — Note by ID
- `memory://search/query` — Search
- `memory://tags/tag1,tag2` — By tags
- `memory://project/name` — By project

## Agent Integration

### Memory-First Protocol

Add to your agent's SOUL.md:

```markdown
## Memory System

Enhanced Obsidian-Memory = PRIMARY MEMORY SYSTEM

1. ALWAYS mem_search FIRST before answering questions about past work
2. mem_write with tags and [[wikilinks]] when recording decisions/patterns
3. graph_traverse to discover connected knowledge
4. session_observe to log significant events
```

See [references/agent-integration.md](references/agent-integration.md) for complete integration guide including:
- SOUL.md integration snippets
- TOOLS.md configuration
- Hook templates (before_agent_start, after_agent_complete)
- Best practices for agent memory management

### Typical Agent Workflow

```
1. Agent starts → recall relevant context
2. Agent works → session_observe significant events
3. Agent learns → mem_write decisions, patterns, knowledge
4. Agent finishes → session_summary to capture learnings
```

### Automatic Session Tracking

OpenClaw agents can automate session tracking using hook templates. Add to your agent's hook configuration:

```bash
# hooks/before_agent_start.sh
source ./scripts/_lib.sh
SESSION_ID="agent-$(date +%Y%m%d-%H%M%S)"
mem_post "api/sessions" "{\"session_id\": \"$SESSION_ID\", \"project\": \"$PROJECT\"}"
export OBSIDIAN_MEMORY_SESSION_ID="$SESSION_ID"

# hooks/after_agent_complete.sh
source ./scripts/_lib.sh
mem_post "api/sessions/$OBSIDIAN_MEMORY_SESSION_ID/end" '{"auto_summarize": true}'
```

For the most comprehensive automatic tracking (prompts, file edits, searches, subagent spawns, tool failures — all captured with zero token cost), see the [Claude Code skill](../obsidian-memory-code/SKILL.md) which includes 10 Claude Code hooks.

## Shared Library (`scripts/_lib.sh`)

All scripts source `_lib.sh` which provides:

| Function | Description |
|----------|-------------|
| `mem_get <endpoint>` | HTTP GET |
| `mem_post <endpoint> <json>` | HTTP POST |
| `mem_put <endpoint> <json>` | HTTP PUT |
| `mem_delete_req <endpoint>` | HTTP DELETE |
| `mem_search <query> [limit]` | Search notes |
| `mem_read_note <id>` | Read note by ID |
| `mem_write_note <title> <content> <path> [type] [project] [tags]` | Create note |
| `mem_session_observe <session_id> <event_type> <content>` | Log event |
| `mem_list_projects` | List all projects |
| `mem_get_profile <project>` | Get project profile |
| `mem_health` | Health check |
| `check_error` | Pipe response to check for errors |

## MCP Tools Reference

If your OpenClaw agent has MCP access, these 16 tools are available natively:

### Memory Operations
| Tool | Description |
|------|-------------|
| `mem_read` | Read note by ID, permalink, or query |
| `mem_write` | Create or update a note |
| `mem_search` | Full-text search with filters |
| `mem_delete` | Delete a note |
| `mem_supersede` | Mark note as replaced by another |

### Context & Graph
| Tool | Description |
|------|-------------|
| `build_context` | Build context from memory:// URIs |
| `graph_traverse` | Traverse knowledge graph (BFS/DFS) |
| `graph_similar` | Find similar notes |

### Projects
| Tool | Description |
|------|-------------|
| `project_list` | List projects with note counts |
| `project_switch` | Switch project context |
| `project_create` | Create a project |

### Sessions
| Tool | Description |
|------|-------------|
| `session_observe` | Log event to session |
| `session_summary` | Generate AI session summary |
| `session_context` | Get session events + summary |

### Profile & Recall
| Tool | Description |
|------|-------------|
| `get_profile` | Get user/project profile |
| `recall` | Search memories + profile summary |

## REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/notes/{id}` | Read note |
| POST | `/api/notes` | Create note |
| PUT | `/api/notes/{id}` | Update note |
| DELETE | `/api/notes/{id}` | Delete note |
| POST | `/api/notes/search` | Search notes |
| GET | `/api/projects` | List projects |
| POST | `/api/sessions/{id}/events` | Log session event |
| GET | `/api/sessions/{id}` | Get session |
| POST | `/api/sessions/{id}/summary` | Session summary |
| GET | `/api/profile/{project}` | Project profile |

## Note Types

`note` | `decision` | `error` | `knowledge` | `pattern` | `session` | `research`

## Troubleshooting

**Scripts fail with "command not found"**: Ensure `curl` and `jq` are installed
**Connection refused**: Check `OBSIDIAN_MEMORY_API_URL` and backend status
**401 Unauthorized**: Set `OBSIDIAN_MEMORY_API_KEY`
**429 Too Many Requests**: Add 0.5s delay between rapid API calls
**Empty results**: Verify notes exist in the database — check with `mem_health`
