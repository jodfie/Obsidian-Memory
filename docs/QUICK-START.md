# Quick Start Guide

Get Obsidian-Memory running in 5 minutes.

## Prerequisites

- Docker and Docker Compose
- An Obsidian vault (or any directory with markdown files)

## Option 1: Docker (Recommended)

### 1. Clone and Configure

```bash
git clone https://github.com/jodfie/Obsidian-Memory.git
cd Obsidian-Memory

# Copy environment template
cp .env.example .env
```

### 2. Edit Configuration

Edit `.env` with your settings:

```bash
# Required: Path to your vault(s)
VAULT_PATH=/path/to/your/vaults

# Optional: Enable AI features
ANTHROPIC_API_KEY=your-api-key

# Optional: Authentication
REQUIRE_AUTH=false
API_TOKEN=your-secret-token
```

### 3. Start Services

```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 4. Verify Installation

```bash
# Check health
curl http://localhost:8765/health

# Expected response:
# {"status":"healthy","vault_connected":true}
```

## Option 2: Manual Installation

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"

# Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload
```

### MCP Server Setup

```bash
cd mcp-server
bun install

# Start MCP server (stdio mode for Claude Code)
bun run src/index.ts

# Or SSE mode for remote access
MCP_TRANSPORT=sse MCP_SSE_PORT=3000 bun run src/index.ts
```

## Register Your First Vault

After starting the services, register a vault:

```bash
curl -X POST "http://localhost:8765/api/vaults" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-vault", "path": "/path/to/vault"}'
```

Or via the API docs at `http://localhost:8765/docs`.

## Connect Claude Code

Add to your Claude Code MCP configuration (`~/.claude.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "command": "bun",
      "args": ["run", "/path/to/Obsidian-Memory/mcp-server/src/index.ts"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "OBSIDIAN_MEMORY_API_URL": "http://localhost:8765"
      }
    }
  }
}
```

## Connect Claude.ai

For Claude.ai integration with the hosted instance:

1. Go to Claude.ai Settings → Integrations → Add MCP Server
2. Configure:
   - **Name**: Obsidian-Memory
   - **Server URL**: `https://memory.redleif.dev/mcp`
   - **Authentication**: OAuth 2.0
   - **Client ID**: `996ac4873739812cad6edd18fbd572b150b5e0bea38fa30299b8e3f393fb6a22`
   - **Authorization URL**: `https://redleif.cloudflareaccess.com/cdn-cgi/access/authorize`
   - **Token URL**: `https://redleif.cloudflareaccess.com/cdn-cgi/access/token`

See [Claude.ai Integration](CLAUDE-AI-INTEGRATION.md) for detailed setup.

## Test MCP Tools

Once connected, test the tools:

```
# In Claude Code or Claude.ai
Use mem_search to find notes about "python"
```

## Next Steps

- [Architecture Overview](ARCHITECTURE.md) - Understand the system design
- [API Reference](api.md) - Full REST API documentation
- [MCP Tools](../mcp-server/README.md) - Complete MCP tool reference
- [Authentication](AUTHENTICATION.md) - Configure auth for production

## Troubleshooting

### "vault_connected": false

The backend can't find or access your vault:

```bash
# Check vault path exists and is readable
ls -la /path/to/your/vault

# Verify VAULT_PATH environment variable
docker exec memory env | grep VAULT

# Check container permissions
docker exec memory ls -la /vaults
```

### MCP Connection Failed

```bash
# Check MCP server health
curl http://localhost:3000/health

# Check backend health
curl http://localhost:8765/health

# View logs
docker logs memory
docker logs memory-mcp
```

### Empty Database

If the database shows 0 notes:

1. Verify vault is registered
2. Check that `_claude-mem/` folder exists in vault (created on first write)
3. Trigger an index refresh via API

See [Troubleshooting](TROUBLESHOOTING.md) for more solutions.
