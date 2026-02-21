---
name: obsidian-memory-codex
description: Obsidian-Memory integration for Codex CLI. Provides bash scripts to search, read, write, and recall notes via REST API. No MCP required — pure HTTP calls using curl and jq.
---

# Obsidian-Memory for Codex

Integration skill for using **Obsidian-Memory** from the **OpenAI Codex CLI**. Since Codex does not support MCP, this skill provides bash scripts that interact with the Obsidian-Memory REST API directly.

## Prerequisites

- `curl` and `jq` installed
- Obsidian-Memory backend running (Docker or local)
- Environment variables set:

```bash
export OBSIDIAN_MEMORY_API_URL="https://memory.example.com/api"
export OBSIDIAN_MEMORY_API_KEY="your-api-key"  # if auth enabled
```

## Scripts

### `scripts/search.sh` — Search Notes

```bash
# Basic search
./scripts/search.sh "authentication patterns"

# With limit
./scripts/search.sh "docker deployment" 5

# Filter by project
./scripts/search.sh "API design" 10 "TechKB"

# Filter by note type
./scripts/search.sh "database" 10 "" "decision"
```

### `scripts/read_note.sh` — Read a Note

```bash
# Read by ID
./scripts/read_note.sh 42

# Read by search query (returns first match)
./scripts/read_note.sh "redis caching pattern"
```

### `scripts/write_note.sh` — Create a Note

```bash
# Basic note
./scripts/write_note.sh "Redis Caching" "## Pattern\n\nUse Redis for..." "patterns/redis.md"

# With type and project
./scripts/write_note.sh "Use PostgreSQL" "Chose PG for ACID..." "decisions/db.md" "decision" "api-project"

# With tags
./scripts/write_note.sh "Auth Flow" "JWT-based auth..." "patterns/auth.md" "pattern" "api" "auth,security,jwt"
```

### `scripts/session_log.sh` — Log Session Event

```bash
# Log a decision
./scripts/session_log.sh "codex-2026-02-18" "decision" "Chose REST over GraphQL for simplicity"

# Log an error
./scripts/session_log.sh "codex-2026-02-18" "error" "PostgreSQL connection timeout on cold start"

# Log a solution
./scripts/session_log.sh "codex-2026-02-18" "solution" "Added connection pool warmup on startup"
```

Event types: `observation`, `decision`, `error`, `solution`, `tool_use`, `file_edit`, `command`, `research`, `user_prompt`

### `scripts/recall.sh` — Quick Recall

```bash
# Search and display results
./scripts/recall.sh "authentication"

# With project profile
./scripts/recall.sh "deployment" "TechKB"
```

## Using with Codex CLI

### Direct Execution

```bash
codex exec ./scripts/search.sh "authentication patterns"
codex exec ./scripts/recall.sh "docker" "TechKB"
```

### In Codex Sessions

Reference the scripts in your Codex prompts:

```bash
codex review -s read-only \
  -m gpt-5.1-codex-max \
  "Search the knowledge base for authentication patterns and summarize. Use: ./brain/skills/obsidian-memory-codex/scripts/search.sh 'auth'"
```

## Shared Library (`scripts/_lib.sh`)

All scripts source `_lib.sh` which provides:

- `mem_get <endpoint>` — HTTP GET
- `mem_post <endpoint> <json_data>` — HTTP POST
- `mem_put <endpoint> <json_data>` — HTTP PUT
- `mem_delete <endpoint>` — HTTP DELETE
- `mem_search <query> [limit]` — Search notes
- `mem_read_note <id>` — Read note by ID
- `mem_write_note <title> <content> <path> [type] [project] [tags_csv]` — Create note
- `mem_session_observe <session_id> <event_type> <content>` — Log session event
- `mem_health` — Check API health
- `check_error` — Pipe response through to check for errors

### Using in Custom Scripts

```bash
#!/usr/bin/env bash
source "/path/to/scripts/_lib.sh"

# Search and process results
results=$(mem_search "my query" 5)
echo "$results" | jq '.results[].title'

# Write a note
mem_write_note "Title" "Content here" "path/to/note.md" "knowledge" "myproject" "tag1,tag2"
```

## All Available Operations

The Obsidian-Memory system provides 16 operations. The scripts above cover the most common ones. All operations are accessible via REST API:

### Memory Operations
| Operation | Script | REST Endpoint |
|-----------|--------|---------------|
| `mem_read` | `read_note.sh` | `GET /api/notes/{id}` |
| `mem_write` | `write_note.sh` | `POST /api/notes` |
| `mem_search` | `search.sh` | `POST /api/notes/search` |
| `mem_delete` | — | `DELETE /api/notes/{id}` |
| `mem_supersede` | — | `POST /api/notes/{id}/supersede` |

### Context & Graph
| Operation | Script | REST Endpoint |
|-----------|--------|---------------|
| `build_context` | — | `POST /api/context` |
| `graph_traverse` | — | `POST /api/graph/traverse` |
| `graph_similar` | — | `POST /api/graph/similar` |

### Projects
| Operation | Script | REST Endpoint |
|-----------|--------|---------------|
| `project_list` | — | `GET /api/projects` |
| `project_switch` | — | `GET /api/projects/{name}` |
| `project_create` | — | `POST /api/projects` |

### Sessions
| Operation | Script | REST Endpoint |
|-----------|--------|---------------|
| `session_observe` | `session_log.sh` | `POST /api/sessions/{id}/events` |
| `session_summary` | — | `POST /api/sessions/{id}/summary` |
| `session_context` | — | `GET /api/sessions/{id}` |

### Profile & Recall
| Operation | Script | REST Endpoint |
|-----------|--------|---------------|
| `get_profile` | `recall.sh` (partial) | `GET /api/profile/{project}` |
| `recall` | `recall.sh` | `POST /api/notes/search` + `GET /api/profile/{project}` |

## Automatic Session Tracking

Codex does not support hooks natively, so session tracking requires explicit `session_log.sh` calls. However, you can wrap Codex invocations in a shell script to automate session lifecycle:

```bash
#!/usr/bin/env bash
# codex-with-memory.sh — wraps codex exec with session tracking
source ./scripts/_lib.sh

SESSION_ID="codex-$(date +%Y%m%d-%H%M%S)"
mem_post "api/sessions" "{\"session_id\": \"$SESSION_ID\"}"

# Run the actual codex command
codex exec "$@"
EXIT_CODE=$?

# End session with summary
mem_post "api/sessions/$SESSION_ID/end" '{"auto_summarize": true}'
exit $EXIT_CODE
```

For fully automatic session tracking (prompts, file edits, searches captured with zero effort), see the [Claude Code skill](../obsidian-memory-code/SKILL.md) which includes 10 Claude Code hooks.

## Troubleshooting

**"curl: command not found"**: Install curl via your package manager
**"jq: command not found"**: Install jq (`apt install jq` / `brew install jq`)
**Connection refused**: Check `OBSIDIAN_MEMORY_API_URL` and that the backend is running
**401 Unauthorized**: Set `OBSIDIAN_MEMORY_API_KEY` environment variable
**429 Too Many Requests**: Add delays between rapid calls (0.5s recommended)
