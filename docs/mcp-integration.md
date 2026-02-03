# MCP Server Integration Guide

This guide explains how to integrate the Obsidian-Memory MCP server with Cursor and Claude.ai.

## Overview

The Obsidian-Memory MCP server is accessible via:
- **Development**: `https://memory-dev.redleif.dev/mcp`
- **Production**: `https://memory.redleif.dev/mcp`

The server uses Server-Sent Events (SSE) transport and is protected by Cloudflare Access OAuth 2.0.

## Cloudflare Access Setup

### 1. Configure Cloudflare Access Application

1. Go to Cloudflare Zero Trust Dashboard
2. Navigate to **Access** → **Applications**
3. Click **Add an application**
4. Select **Self-hosted**
5. Configure:
   - **Application name**: `Obsidian-Memory Dev` (or `Obsidian-Memory Prod`)
   - **Application domain**: `memory-dev.redleif.dev` (or `memory.redleif.dev`)
   - **Session duration**: Choose appropriate duration
6. Add **Policy**:
   - **Policy name**: `Allow authenticated users`
   - **Action**: Allow
   - **Include**: Email domain (e.g., `@redleif.dev`) or specific emails
7. Save the application

### 2. Configure Traefik to Forward Cloudflare Access Headers

Ensure Traefik is configured to forward Cloudflare Access headers. The middleware should:
- Forward `CF-Access-JWT` header
- Forward `CF-Access-JWT-Assertion` header
- Set `X-Forwarded-Proto: https`

### 3. Environment Variables

Set in `.env.dev` or `.env.prod`:

```bash
CLOUDFLARE_ACCESS_ENABLED=true
CLOUDFLARE_ACCESS_TEAM_DOMAIN=redleif.cloudflareaccess.com
```

## Claude.ai Integration

### Add MCP Server to Claude.ai

1. Open Claude.ai
2. Go to **Settings** → **Integrations** → **MCP Servers**
3. Click **Add Server**
4. Configure:
   - **Name**: `Obsidian-Memory`
   - **Server URL**: `https://memory.redleif.dev/mcp`
   - **Authentication**:
     - Type: `OAuth 2.0`
     - Client ID: `996ac4873739812cad6edd18fbd572b150b5e0bea38fa30299b8e3f393fb6a22`
     - Client Secret: `pkce_no_secret_required`
     - Authorization URL: `https://redleif.cloudflareaccess.com/cdn-cgi/access/authorize`
     - Token URL: `https://redleif.cloudflareaccess.com/cdn-cgi/access/token`
5. Click **Save** and authorize when prompted

**Note**: The server URL is `/mcp` (not `/mcp/sse`). The SSE endpoints are handled automatically by the MCP protocol.

### Testing in Claude.ai

Once configured, you can use MCP tools in Claude.ai:

```
@obsidian-memory mem_search query="python async"
```

## Cursor Integration

### Quick add (this project)

This repo includes a Cursor MCP config. Open the project in Cursor and the Obsidian-Memory server is available:

- **Config file**: `.cursor/mcp.json`
- **URL**: `https://memory.redleif.dev/mcp` (Streamable HTTP; Cursor auto-detects transport)

If your instance is behind Cloudflare Access, use **Settings → MCP → obsidian-memory → Login** (or `agent mcp login obsidian-memory` in the CLI). For static OAuth, add an `auth` block to `mcp.json` (see below).

### Cursor configuration options

**1. Remote (recommended)** – use the deployed MCP endpoint (already in `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "url": "https://memory.redleif.dev/mcp",
      "headers": {}
    }
  }
}
```

**2. Remote + static OAuth** (e.g. Cloudflare Access with fixed client credentials):

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "url": "https://memory.redleif.dev/mcp",
      "auth": {
        "CLIENT_ID": "your-oauth-client-id",
        "CLIENT_SECRET": "your-oauth-client-secret"
      }
    }
  }
}
```

Register redirect URI in your OAuth provider: `cursor://anysphere.cursor-mcp/oauth/callback`.

**3. Local stdio** – run MCP server locally and point it at your backend:

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "command": "bun",
      "args": ["run", "mcp-server/src/index.ts"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "OBSIDIAN_MEMORY_API_URL": "http://localhost:8765"
      }
    }
  }
}
```

**4. Local remote** – backend + MCP running via Docker, Cursor talks to localhost:

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "url": "http://localhost:8765/mcp"
    }
  }
}
```

Config locations: project `.cursor/mcp.json` (project-specific) or global `~/.cursor/mcp.json`.

## MCP Endpoints

### SSE Endpoint
- **URL**: `https://memory-dev.redleif.dev/mcp/sse`
- **Method**: `GET`
- **Purpose**: Server-Sent Events stream for receiving messages from MCP server

### Message Endpoint
- **URL**: `https://memory-dev.redleif.dev/mcp/message`
- **Method**: `POST`
- **Purpose**: Send JSON-RPC requests to MCP server
- **Content-Type**: `application/json`

### Health Check
- **URL**: `https://memory-dev.redleif.dev/mcp/health`
- **Method**: `GET`
- **Purpose**: Check MCP server health

## Available MCP Tools

The server provides the following tools:

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

## Troubleshooting

### Cloudflare Access Issues

If you get authentication errors:

1. Verify Cloudflare Access application is configured correctly
2. Check that your email is in the access policy
3. Verify `CF-Access-JWT` header is being forwarded by Traefik
4. Check Cloudflare Access logs in Zero Trust dashboard

### MCP Connection Issues

If MCP server doesn't connect:

1. Check MCP server health: `curl https://memory-dev.redleif.dev/mcp/health`
2. Verify MCP server container is running: `docker ps | grep mcp`
3. Check MCP server logs: `docker logs memory-mcp-dev`
4. Verify network connectivity between containers

### CORS Issues

If you see CORS errors:

1. Verify CORS headers are set correctly in MCP proxy endpoint
2. Check that Cloudflare Access is not blocking preflight requests
3. Ensure `Access-Control-Allow-Origin` header is present

## Security Notes

- Cloudflare Access provides OAuth 2.0 authentication
- All requests to `/mcp/*` endpoints require valid Cloudflare Access JWT
- The MCP server runs in an isolated Docker container
- Internal communication between containers uses Docker network (not exposed)
- Traefik handles SSL/TLS termination

## Development vs Production

### Development
- URL: `https://memory-dev.redleif.dev/mcp`
- MCP Server Container: `memory-mcp-dev`
- Backend Container: `memory-dev`
- Hot reload enabled for backend

### Production
- URL: `https://memory.redleif.dev/mcp`
- MCP Server Container: `memory-mcp`
- Backend Container: `memory`
- Resource limits applied
- Log rotation enabled
