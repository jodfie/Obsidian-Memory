# Obsidian-Memory MCP Server API Reference

## Overview

The Obsidian-Memory MCP Server provides HTTP-based access to memory operations for an Obsidian vault. It implements a subset of the MCP (Model Context Protocol) over HTTPS for remote access.

## Authentication

All requests require Bearer token authentication:

```bash
Authorization: Bearer your-api-key-here
```

## Base URL

Default: `http://localhost:3001` (or your configured domain)

## Endpoints

### Health Check

```http
GET /health
```

Returns server status and configuration.

**Response:**
```json
{
  "status": "healthy",
  "vault": "/path/to/vault",
  "timestamp": "2024-01-27T18:00:00.000Z"
}
```

### MCP Protocol

```http
POST /mcp
Content-Type: application/json
Authorization: Bearer your-api-key
```

All MCP operations use the same endpoint with different method names.

## MCP Methods

### memory_search

Search across memory files for specific content.

**Request:**
```json
{
  "method": "memory_search",
  "params": {
    "query": "browser automation",
    "maxResults": 10
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "path": "MEMORY.md",
      "line": 45,
      "content": "Browser automation using verify-on-browser skill",
      "score": 0.8
    },
    {
      "path": "memory/2024-01-27.md",
      "line": 23,
      "content": "Successfully tested browser automation with Google.com",
      "score": 0.7
    }
  ]
}
```

### memory_get

Retrieve content from a specific memory file.

**Request:**
```json
{
  "method": "memory_get",
  "params": {
    "path": "MEMORY.md",
    "from": 10,
    "lines": 20
  }
}
```

**Parameters:**
- `path`: File path relative to vault root
- `from`: Starting line number (optional)
- `lines`: Number of lines to read (optional)

**Response:**
```json
{
  "content": "# MEMORY.md - Long-Term Memory\n\n## Recent Projects...",
  "lines": 20,
  "totalLines": 150
}
```

### memory_write

Write content to a memory file.

**Request:**
```json
{
  "method": "memory_write",
  "params": {
    "path": "memory/2024-01-27.md",
    "content": "## New Discovery\n\nFound interesting browser automation technique...",
    "append": true
  }
}
```

**Parameters:**
- `path`: File path relative to vault root
- `content`: Content to write
- `append`: Whether to append (true) or overwrite (false)

**Response:**
```json
{
  "success": true,
  "path": "memory/2024-01-27.md"
}
```

### memory_log

Quick log entry to today's memory file.

**Request:**
```json
{
  "method": "memory_log",
  "params": {
    "content": "Successfully deployed MCP server to production",
    "category": "Deployment"
  }
}
```

**Parameters:**
- `content`: Content to log
- `category`: Optional category/section heading

**Response:**
```json
{
  "success": true,
  "file": "memory/2024-01-27.md"
}
```

### list_tools

Get available MCP tools and their schemas.

**Request:**
```json
{
  "method": "list_tools"
}
```

**Response:**
```json
{
  "tools": [
    {
      "name": "memory_search",
      "description": "Search memory files for content",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string",
            "description": "Search query"
          },
          "maxResults": {
            "type": "number",
            "description": "Max results to return"
          }
        },
        "required": ["query"]
      }
    }
  ]
}
```

## Error Handling

All errors return appropriate HTTP status codes with JSON error messages:

```json
{
  "error": "File not found: nonexistent.md"
}
```

Common status codes:
- `401`: Unauthorized (invalid API key)
- `400`: Bad request (invalid method or parameters)
- `404`: File not found
- `500`: Server error

## Rate Limiting

Currently no rate limiting is implemented. Consider implementing rate limiting for production use.

## Security Considerations

- Always use HTTPS in production
- Store API keys securely
- Consider IP whitelisting for additional security
- Regular key rotation recommended
- File system access is limited to the vault directory