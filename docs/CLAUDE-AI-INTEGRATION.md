# Claude.ai Integration Guide

Complete guide for connecting Claude.ai to your Obsidian-Memory MCP server.

## Overview

Claude.ai can connect to your Obsidian-Memory instance via the MCP (Model Context Protocol) to access your persistent knowledge base across conversations.

**Connection Type**: Remote MCP over SSE (Server-Sent Events)
**Authentication**: OAuth 2.0 via Cloudflare Access

## Prerequisites

- Obsidian-Memory deployed and accessible via HTTPS
- Cloudflare Access configured for authentication
- OAuth credentials (Client ID and Client Secret)

## Connection Details

For the public instance at `memory.example.com`:

| Setting | Value |
|---------|-------|
| **Server URL** | `https://memory.example.com/mcp` |
| **OAuth Client ID** | `your-oauth-client-id` |
| **OAuth Client Secret** | `pkce_no_secret_required` (PKCE mode) |
| **Authorization URL** | `https://your-team.cloudflareaccess.com/cdn-cgi/access/authorize` |
| **Token URL** | `https://your-team.cloudflareaccess.com/cdn-cgi/access/token` |

## Step-by-Step Setup

### Step 1: Access Claude.ai Settings

1. Log in to [Claude.ai](https://claude.ai)
2. Click your profile icon (bottom left)
3. Select **Settings**
4. Navigate to **Integrations** tab
5. Find **MCP Servers** section

### Step 2: Add MCP Server

Click **Add MCP Server** and fill in the details:

**Basic Configuration**:
```
Name: Obsidian-Memory
Description: Persistent memory system with knowledge graph
Server URL: https://memory.example.com/mcp
Transport: SSE (Server-Sent Events)
```

**Authentication Configuration**:
```
Authentication Type: OAuth 2.0
OAuth Provider: Custom
Client ID: your-oauth-client-id
Client Secret: pkce_no_secret_required
Authorization URL: https://your-team.cloudflareaccess.com/cdn-cgi/access/authorize
Token URL: https://your-team.cloudflareaccess.com/cdn-cgi/access/token
Scope: (leave empty - uses default scopes)
```

### Step 3: Authorize Connection

1. Click **Save** or **Connect**
2. You'll be redirected to Cloudflare Access login
3. Enter your email (must be authorized in the Cloudflare Access policy)
4. Check your email for the one-time code
5. Enter the code to complete authentication
6. You'll be redirected back to Claude.ai

### Step 4: Verify Connection

Once connected, you should see:
- ✅ Green checkmark next to Obsidian-Memory
- "Connected" status
- Available tools listed

Test the connection:
```
Can you search my memory for notes about "python"?
```

Claude should respond using the `mem_search` tool.

## Available Tools in Claude.ai

Once connected, these tools are available:

### Memory Management
- **mem_read**: Read a specific note by ID or permalink
- **mem_write**: Create or update notes
- **mem_search**: Search notes with full-text search
- **mem_supersede**: Mark a note as superseded by another

### Knowledge Graph
- **graph_traverse**: Navigate the knowledge graph
- **graph_similar**: Find similar notes

### Project Management
- **project_list**: View all projects
- **project_switch**: Switch to a project context
- **project_create**: Create new projects

### Session Tracking
- **session_observe**: Add observations to the current session
- **session_summary**: Get AI-generated session summaries
- **session_context**: Retrieve session context

### Context Building
- **build_context**: Build context from memory:// URIs

## Using Memory Tools in Claude.ai

### Reading Notes

```
Can you read the note with permalink "python-async-patterns"?
```

Claude will use `mem_read`:
```json
{
  "permalink": "python-async-patterns"
}
```

### Searching Memory

```
Search my memory for all notes about React hooks
```

Claude will use `mem_search`:
```json
{
  "query": "React hooks",
  "response_format": "markdown"
}
```

### Creating Notes

```
Create a note titled "Meeting Notes - Jan 2024" with content about our discussion
```

Claude will use `mem_write`:
```json
{
  "title": "Meeting Notes - Jan 2024",
  "content": "# Meeting Notes - Jan 2024\n\n...",
  "note_type": "note",
  "tags": ["meetings", "2024"]
}
```

### Graph Navigation

```
Show me notes related to my "authentication" note
```

Claude will use `graph_traverse`:
```json
{
  "start_note_id": 42,
  "max_depth": 2,
  "algorithm": "bfs"
}
```

## OAuth Flow Explanation

### What Happens During Authorization

1. **Initiation**: Claude.ai redirects to Cloudflare Access
2. **Authentication**: You prove your identity (email + code)
3. **Authorization**: Cloudflare grants access token
4. **Token Exchange**: Claude.ai receives access token
5. **API Access**: Token included in all MCP requests

### Token Lifecycle

- **Duration**: Tokens expire after 24 hours (configurable)
- **Refresh**: Claude.ai automatically refreshes tokens
- **Revocation**: Disconnect in Claude.ai settings to revoke

### Security

- **PKCE**: Uses PKCE (Proof Key for Code Exchange) for enhanced security
- **No Client Secret**: The "secret" value is a placeholder - PKCE provides security
- **Email Verification**: Only authorized emails can connect
- **Token Scope**: Tokens are scoped to MCP API access only

## Troubleshooting

### "Failed to Connect"

**Possible Causes**:
1. Server URL incorrect
2. Server not responding
3. Network/firewall issues

**Solutions**:
```bash
# Test server accessibility
curl https://memory.example.com/mcp/health

# Expected response:
# {"status":"ok"}
```

### "Authentication Failed"

**Possible Causes**:
1. Email not authorized in Cloudflare Access policy
2. OAuth credentials incorrect
3. Token expired

**Solutions**:
1. Verify your email is in the allowed list (Cloudflare Zero Trust dashboard)
2. Double-check Client ID matches exactly
3. Disconnect and reconnect to get fresh token

### "No Tools Available"

**Possible Causes**:
1. MCP server not responding
2. Backend API unavailable
3. Connection not fully established

**Solutions**:
```bash
# Check MCP server health
curl https://memory.example.com/mcp/health

# Check backend health
curl https://memory.example.com/health

# View MCP server logs (if you have access)
docker logs memory-mcp
```

### Tools Return Errors

**Common Errors**:

**"Note not found"**:
- Note ID/permalink doesn't exist
- Try `mem_search` first to find notes

**"Unauthorized"**:
- Token expired - disconnect and reconnect
- Email not in access policy

**"Invalid request"**:
- Missing required parameters
- Check tool input schema

### Testing Connection

Ask Claude to test each tool:

```
Please test these tools one by one and tell me which ones work:
1. mem_search - search for "test"
2. project_list - list all projects
3. graph_traverse - if any notes exist, traverse from one
```

## Advanced Usage

### Context Loading

Load relevant context at conversation start:

```
Load context from my memory about [topic] before we discuss it
```

### Session Tracking

Track important decisions:

```
Remember this decision in the current session: [decision details]
```

### Knowledge Graph Queries

Explore connections:

```
What topics are connected to [topic] in my knowledge graph?
```

### Cross-Project Context

Switch between projects:

```
Switch to my "work" project and search for [query]
```

## Best Practices

### 1. Initialize Context
Start conversations by loading relevant memory:
```
Before we start, search my memory for notes about [topic]
```

### 2. Save Key Information
Store important insights during conversations:
```
Save this solution to my memory as "How to [problem]"
```

### 3. Link Related Concepts
Create wikilinks to connect ideas:
```
Create a note about [topic] and link it to [[existing-note]]
```

### 4. Use Tags
Organize with tags:
```
Save this as a note tagged with "python", "async", "patterns"
```

### 5. Track Sessions
Log important events:
```
Observe this event in the current session: [event details]
```

## Privacy and Data

### What Data is Sent

When using MCP tools, Claude.ai sends:
- Tool names and parameters
- Your queries and commands
- OAuth access token

### What Data is Stored

Obsidian-Memory stores:
- Notes you create or update
- Session events you observe
- Graph relationships between notes

### Data Location

- **Your Instance**: Data stored in your vaults on your infrastructure
- **Anthropic**: Tool usage logs (per Anthropic privacy policy)
- **Cloudflare**: Authentication logs (per Cloudflare privacy policy)

## Self-Hosting for Claude.ai

To use Claude.ai with your own instance:

### 1. Deploy Obsidian-Memory

Follow [Deployment Guide](deployment.md) to deploy with:
- HTTPS endpoint (required for Claude.ai)
- Cloudflare Access configured
- MCP server in SSE mode

### 2. Configure Cloudflare Access

Set up OAuth application:
1. Go to Cloudflare Zero Trust → Access → Applications
2. Create Self-hosted application
3. Enable **OpenID Connect (OIDC)**
4. Note the Client ID
5. Add redirect URIs:
   - `https://claude.ai/api/mcp/auth_callback`
   - `https://claude.com/api/mcp/auth_callback`

### 3. Environment Variables

Set in your deployment:
```bash
# Enable Cloudflare Access
CLOUDFLARE_ACCESS_ENABLED=true
CLOUDFLARE_ACCESS_TEAM_DOMAIN=your-team.cloudflareaccess.com

# OAuth Configuration
CLOUDFLARE_OAUTH_CLIENT_ID=your-client-id
CLOUDFLARE_OAUTH_CLIENT_SECRET=pkce_no_secret_required
```

### 4. Share Connection Details

Provide users with:
- Server URL: `https://your-domain.com/mcp`
- Client ID (from Cloudflare Access)
- Authorization URL: `https://your-team.cloudflareaccess.com/cdn-cgi/access/authorize`
- Token URL: `https://your-team.cloudflareaccess.com/cdn-cgi/access/token`

## Support

For issues:
1. Check [Troubleshooting Guide](TROUBLESHOOTING.md)
2. Review server logs
3. Open issue on [GitHub](https://github.com/jodfie/Obsidian-Memory/issues)

## Related Documentation

- [MCP Integration Guide](mcp-integration.md)
- [Authentication Guide](AUTHENTICATION.md)
- [API Reference](api.md)
- [Architecture Overview](ARCHITECTURE.md)
