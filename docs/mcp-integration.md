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
2. Go to **Settings** → **MCP Servers**
3. Click **Add Server**
4. Configure:
   - **Name**: `Obsidian-Memory`
   - **Transport**: `SSE (Server-Sent Events)`
   - **URL**: `https://memory-dev.redleif.dev/mcp/sse`
   - **Authentication**: 
     - Type: `OAuth 2.0`
     - Provider: `Cloudflare Access`
     - Client ID: (from Cloudflare Access application)
     - Client Secret: (from Cloudflare Access application)
     - Authorization URL: `https://redleif.cloudflareaccess.com/cdn-cgi/access/login`
     - Token URL: `https://redleif.cloudflareaccess.com/cdn-cgi/access/token`
5. Save the configuration

### Testing in Claude.ai

Once configured, you can use MCP tools in Claude.ai:

```
@obsidian-memory mem_search query="python async"
```

## Cursor Integration

### Add MCP Server to Cursor

1. Open Cursor Settings
2. Navigate to **Features** → **MCP Servers**
3. Click **Add Server**
4. Configure:
   - **Name**: `obsidian-memory`
   - **Command**: (for local stdio transport)
     ```json
     {
       "command": "bun",
       "args": ["run", "/path/to/mcp-server/src/index.ts"],
       "env": {
         "MCP_TRANSPORT": "stdio",
         "OBSIDIAN_MEMORY_API_URL": "http://localhost:8765"
       }
     }
     ```
   - Or for remote SSE transport:
     ```json
     {
       "transport": "sse",
       "url": "https://memory-dev.redleif.dev/mcp/sse",
       "auth": {
         "type": "oauth2",
         "provider": "cloudflare",
         "clientId": "...",
         "clientSecret": "..."
       }
     }
     ```

### Cursor Configuration File

Add to `~/.cursor/mcp.json` or project `.cursor/mcp.json`:

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

For remote access:

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "transport": "sse",
      "url": "https://memory-dev.redleif.dev/mcp/sse",
      "auth": {
        "type": "oauth2",
        "provider": "cloudflare",
        "teamDomain": "redleif.cloudflareaccess.com"
      }
    }
  }
}
```

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
