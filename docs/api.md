# API Documentation

Complete API reference for Obsidian-Memory backend.

## Base URL

Default: `http://localhost:8000`

## Authentication

Obsidian-Memory supports multiple authentication methods:

### Bearer Token Authentication

If `REQUIRE_AUTH=true`, include a Bearer token in requests:

```
Authorization: Bearer <your-token>
```

Set the token via the `API_AUTH_TOKEN` environment variable.

### Cloudflare Access (Recommended for Production)

When `CLOUDFLARE_ACCESS_ENABLED=true`, requests are authenticated via Cloudflare Access JWT:

```
CF-Access-JWT: <jwt-token>
```

Configure with these environment variables:
- `CLOUDFLARE_ACCESS_TEAM_DOMAIN` - Your Cloudflare Access team domain
- `CLOUDFLARE_ACCESS_AUDIENCE` - Application audience tag (AUD)

See [AUTHENTICATION.md](AUTHENTICATION.md) for detailed setup instructions.

### OAuth 2.1 (Claude.ai MCP Integration)

For Claude.ai MCP connector integration, OAuth 2.1 with PKCE is supported via the OAuth gateway.
See [AUTHENTICATION.md](AUTHENTICATION.md) for OAuth configuration.

## Endpoints

### Health & Metrics

#### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

#### GET /metrics

System metrics for monitoring.

**Response:**
```json
{
  "status": "ok",
  "memory": {
    "rss": 12345678,
    "vms": 23456789,
    "percent": 2.5
  },
  "cpu": {
    "percent": 1.2
  },
  "threads": 4
}
```

### Notes

#### GET /api/notes

List notes with optional filtering.

**Query Parameters:**
- `vault` (string, optional) - Filter by vault name
- `project` (string, optional) - Filter by project
- `limit` (integer, optional) - Limit results (default: 50)
- `offset` (integer, optional) - Offset for pagination (default: 0)

**Response:**
```json
{
  "notes": [
    {
      "id": 1,
      "vault_name": "my-vault",
      "relative_path": "notes/example.md",
      "permalink": "example",
      "title": "Example Note",
      "note_type": "note",
      "project": "my-project",
      "content": "# Example Note\n\nContent...",
      "tags": ["tag1", "tag2"],
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

#### POST /api/notes

Create a new note.

**Request Body:**
```json
{
  "vault_name": "my-vault",
  "relative_path": "notes/new-note.md",
  "title": "New Note",
  "content": "# New Note\n\nContent...",
  "note_type": "note",
  "project": "my-project",
  "tags": ["tag1"]
}
```

**Response:**
```json
{
  "id": 1,
  "vault_name": "my-vault",
  "relative_path": "notes/new-note.md",
  "permalink": "new-note",
  "title": "New Note",
  "note_type": "note",
  "project": "my-project",
  "content": "# New Note\n\nContent...",
  "tags": ["tag1"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### GET /api/notes/{note_id}

Get a note by ID.

**Response:**
```json
{
  "id": 1,
  "vault_name": "my-vault",
  "relative_path": "notes/example.md",
  "permalink": "example",
  "title": "Example Note",
  "note_type": "note",
  "project": "my-project",
  "content": "# Example Note\n\nContent...",
  "tags": ["tag1"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### PUT /api/notes/{note_id}

Update a note.

**Request Body:**
```json
{
  "title": "Updated Title",
  "content": "# Updated Content\n\nContent...",
  "tags": ["tag1", "tag2"]
}
```

All fields are optional - only provided fields will be updated.

**Response:**
Updated note object (same format as GET).

#### DELETE /api/notes/{note_id}

Delete a note.

**Response:**
```json
{
  "message": "Note deleted"
}
```

#### POST /api/notes/search

Search notes with full-text search.

**Request Body:**
```json
{
  "query": "search terms",
  "vault": "my-vault",
  "project": "my-project",
  "note_type": "note",
  "tags": ["tag1"],
  "tags_any": ["tag2", "tag3"],
  "sort": "relevance",
  "limit": 50,
  "offset": 0
}
```

**Response:**
Same format as GET /api/notes.

#### POST /api/notes/supersede

Mark a note as superseded by another note. Creates bi-directional relationships:
- Old note gets `superseded_by` pointing to new note
- New note gets `supersedes` pointing to old note

This is useful for knowledge evolution tracking when information is updated or replaced.

**Request Body:**
```json
{
  "old_note_id": 1,
  "new_note_id": 2,
  "reason": "Updated with latest findings"
}
```

**Response:**
```json
{
  "old_note_id": 1,
  "new_note_id": 2,
  "old_note_title": "Original Note",
  "new_note_title": "Updated Note",
  "message": "Note 1 marked as superseded by note 2"
}
```

**Error Codes:**
- `400` - Self-supersession not allowed (old_note_id == new_note_id)
- `404` - Note not found
- `409` - Notes are in different vaults

### Projects

#### GET /api/projects

List all projects with note counts.

**Response:**
```json
{
  "projects": [
    {
      "name": "my-project",
      "note_count": 42
    }
  ]
}
```

#### GET /api/projects/{project_name}/notes

List notes for a specific project.

**Query Parameters:**
- `limit` (integer, optional)
- `offset` (integer, optional)

**Response:**
```json
{
  "project": "my-project",
  "notes": [
    {
      "note_id": 1,
      "title": "Note Title",
      "permalink": "note-title",
      "note_type": "note",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total_count": 42,
  "limit": 50,
  "offset": 0
}
```

#### POST /api/projects

Create a new project.

**Request Body:**
```json
{
  "project_name": "new-project"
}
```

**Response:**
```json
{
  "project": "new-project",
  "status": "created",
  "message": "Project created"
}
```

### Sessions

#### GET /api/sessions

List sessions.

**Query Parameters:**
- `project` (string, optional)
- `limit` (integer, optional)

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "abc123",
      "project": "my-project",
      "started_at": "2024-01-01T00:00:00Z",
      "ended_at": "2024-01-01T01:00:00Z",
      "status": "ended",
      "event_count": 42
    }
  ]
}
```

#### POST /api/sessions

Create a new session.

**Request Body:**
```json
{
  "project": "my-project"
}
```

**Response:**
```json
{
  "session_id": "abc123",
  "project": "my-project",
  "started_at": "2024-01-01T00:00:00Z",
  "status": "active"
}
```

#### GET /api/sessions/{session_id}

Get session details.

**Response:**
```json
{
  "session_id": "abc123",
  "project": "my-project",
  "started_at": "2024-01-01T00:00:00Z",
  "ended_at": "2024-01-01T01:00:00Z",
  "status": "ended",
  "event_count": 42,
  "events": [...],
  "summary": {
    "key_learnings": [...],
    "decisions": [...],
    "errors_encountered": [...],
    "solutions_found": [...],
    "next_steps": [...],
    "summary_text": "...",
    "compression_ratio": 0.5
  }
}
```

#### POST /api/sessions/observe

Add an event to a session.

**Request Body:**
```json
{
  "session_id": "abc123",
  "event_type": "file_edit",
  "content": "Edited file.py",
  "metadata": {
    "file": "file.py",
    "tool": "write_file"
  }
}
```

#### POST /api/sessions/{session_id}/summary

Generate AI summary for a session.

**Response:**
```json
{
  "key_learnings": [...],
  "decisions": [...],
  "errors_encountered": [...],
  "solutions_found": [...],
  "next_steps": [...],
  "summary_text": "...",
  "compression_ratio": 0.5
}
```

#### POST /api/sessions/context

Get session context.

**Request Body:**
```json
{
  "session_id": "abc123",
  "include_events": true,
  "include_summary": true,
  "limit": 50
}
```

### Graph

#### GET /api/graph

Get the full knowledge graph.

**Response:**
```json
{
  "nodes": [
    {
      "id": 1,
      "title": "Note Title",
      "permalink": "note-title",
      "vault_name": "my-vault",
      "note_type": "note",
      "project": "my-project",
      "tags": ["tag1"]
    }
  ],
  "edges": [
    {
      "source": 1,
      "target": 2,
      "target_title": "Target Note",
      "type": "wikilink",
      "context": null,
      "weight": 1.0
    }
  ]
}
```

#### GET /api/graph/nodes

List all graph nodes.

#### GET /api/graph/edges

List all graph edges.

#### GET /api/graph/nodes/{node_id}/neighbors

Get neighbors for a node.

### Sync

#### GET /api/sync/status/{vault_name}

Get sync status for a vault.

**Response:**
```json
{
  "vault": "my-vault",
  "status": {
    "is_repo": true,
    "has_remote": true,
    "last_sync_time": "2024-01-01T00:00:00Z",
    "last_sync_device": "Linux-hostname",
    "sync_state": "idle",
    "modified_files": ["file1.md"],
    "untracked_files": ["file2.md"],
    "conflicts": [],
    "pending_changes": 2,
    "device_id": "Linux-hostname"
  }
}
```

#### GET /api/sync/status

Get sync statuses for all vaults.

#### POST /api/sync/init/{vault_name}

Initialize Git repository for a vault.

#### POST /api/sync/remote/{vault_name}

Add or update remote repository.

**Query Parameters:**
- `url` (string, required) - Remote URL
- `name` (string, optional) - Remote name (default: "origin")

#### POST /api/sync/commit/{vault_name}

Commit changes.

**Query Parameters:**
- `message` (string, required) - Commit message
- `author` (string, optional) - Author (format: "Name <email>")

#### POST /api/sync/pull/{vault_name}

Pull changes from remote.

**Query Parameters:**
- `remote` (string, optional) - Remote name (default: "origin")
- `branch` (string, optional) - Branch name (default: "main")

#### POST /api/sync/push/{vault_name}

Push changes to remote.

**Query Parameters:**
- `remote` (string, optional) - Remote name (default: "origin")
- `branch` (string, optional) - Branch name (default: "main")

#### POST /api/sync/sync/{vault_name}

Perform full sync (pull, commit, push).

**Query Parameters:**
- `remote` (string, optional) - Remote name (default: "origin")
- `branch` (string, optional) - Branch name (default: "main")

**Response:**
```json
{
  "vault": "my-vault",
  "pulled": true,
  "committed": true,
  "pushed": true,
  "conflicts": [],
  "updated_files": ["file1.md"],
  "device_id": "Linux-hostname",
  "sync_time": "2024-01-01T00:00:00Z"
}
```

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message",
  "error_type": "ErrorType"
}
```

Common status codes:
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (invalid token)
- `404` - Not Found
- `409` - Conflict (sync conflicts)
- `500` - Internal Server Error
- `503` - Service Unavailable (Git not available, AI unavailable)

## Rate Limiting

Rate limiting protects the API from abuse. When enabled, requests are limited per IP address.

### Configuration

Environment variables:
- `RATE_LIMIT_ENABLED` - Enable/disable rate limiting (default: `true`)
- `RATE_LIMIT_REQUESTS_PER_MINUTE` - Requests allowed per minute (default: `60`)
- `RATE_LIMIT_BURST` - Additional burst allowance (default: `10`)

### Response Headers

All responses include rate limit information:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed per minute |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when the limit resets |

### Rate Limit Exceeded

When the rate limit is exceeded, the API returns:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Remaining: 0

{
  "detail": "Too many requests. Please try again later.",
  "retry_after": 30
}
```

Wait for the `Retry-After` seconds before retrying.

### Exempt Endpoints

The following endpoints are exempt from rate limiting:
- `GET /health` - Health check
- `GET /metrics` - Metrics endpoint

## Request Validation

The API validates all incoming requests for security:

### Path Traversal Protection

Requests containing path traversal patterns are rejected with `400 Bad Request`:
- `../` sequences
- URL-encoded variants (`%2e%2e/`)
- Double-encoded variants

### Content-Type Validation

POST, PUT, and PATCH requests must use valid content types:
- `application/json`
- `application/x-www-form-urlencoded`
- `multipart/form-data`

Invalid content types return `415 Unsupported Media Type`.

### Request Size Limits

Requests exceeding `MAX_REQUEST_SIZE_BYTES` (default: 10 MB) return `413 Request Entity Too Large`.

## Pagination

List endpoints support pagination via `limit` and `offset` query parameters. Default limit is 50.
