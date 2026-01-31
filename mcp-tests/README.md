# MCP Server Testing Harness

Pre-authenticated E2E testing for remote MCP servers with Cloudflare tunnels and OAuth 2.1 authentication.

## Overview

This harness provides automated testing for MCP servers in CI/CD pipelines by:
1. Using pre-obtained OAuth tokens (no browser interaction needed during tests)
2. Supporting Cloudflare Access service token authentication
3. Generating JUnit XML for CI system integration
4. Providing both automated and interactive testing modes

## Quick Start

### 1. Obtain OAuth Tokens (One-Time Manual Step)

```bash
# Install dependencies locally
npm install -g mcp-remote

# Run the token obtainer script
./scripts/obtain-tokens.sh https://your-mcp-server.example.com/sse
```

This opens a browser for OAuth authentication. After completing auth:
- Tokens are saved to `~/.mcp-auth/`
- Script outputs the tokens for CI/CD configuration

### 2. Configure CI/CD Secrets

Add to your CI/CD secrets (GitHub Actions, GitLab CI, etc.):

```
MCP_SERVER_URL=https://your-mcp-server.example.com/sse
MCP_ACCESS_TOKEN=<token from step 1>
```

### 3. Run Tests

```bash
# Local testing with Docker Compose
cp .env.example .env
# Edit .env with your values

docker compose run --rm tests

# Or run specific commands
docker compose run --rm tests list-tools
docker compose run --rm tests test-tool search_notes query="test"
```

## Authentication Methods

### Method 1: OAuth Access Token (Recommended)

Best for servers using standard OAuth 2.1 flows.

```bash
# Set environment variables
export MCP_SERVER_URL="https://mcp.example.com/sse"
export MCP_ACCESS_TOKEN="your-oauth-access-token"
export MCP_REFRESH_TOKEN="optional-refresh-token"

docker compose run --rm tests
```

### Method 2: Cloudflare Access Service Tokens

Best for servers behind Cloudflare Access.

1. Create service token in Cloudflare Zero Trust dashboard:
   - Go to Access > Service Auth > Create Service Token
   - Save the Client ID and Client Secret

2. Configure:
```bash
export MCP_SERVER_URL="https://mcp.example.com/sse"
export CF_ACCESS_CLIENT_ID="your-client-id.access"
export CF_ACCESS_CLIENT_SECRET="your-client-secret"

docker compose run --rm tests
```

### Method 3: Volume-Mounted Auth

Mount the `~/.mcp-auth` directory from a manual OAuth session:

```bash
# After running obtain-tokens.sh
cp -r ~/.mcp-auth ./mcp-auth

# In docker-compose.yml, already configured to mount ./mcp-auth
docker compose run --rm tests
```

## Writing Tests

Create JSON test files in the `tests/` directory:

```json
{
  "name": "My Server Tests",
  "tests": [
    {
      "name": "Check tool exists",
      "type": "list-tools",
      "expect": { "minTools": 1 }
    },
    {
      "name": "Call search tool",
      "type": "call-tool",
      "tool": "search",
      "arguments": { "query": "test" },
      "expect": { "isError": false }
    },
    {
      "name": "Expect error for invalid input",
      "type": "call-tool", 
      "tool": "get_item",
      "arguments": { "id": "nonexistent" },
      "expect": { "isError": true }
    }
  ]
}
```

### Test Types

| Type | Description | Parameters |
|------|-------------|------------|
| `list-tools` | List available tools | `expect.minTools` |
| `list-resources` | List available resources | - |
| `list-prompts` | List available prompts | - |
| `call-tool` | Call a specific tool | `tool`, `arguments`, `expect` |
| `read-resource` | Read a resource | `uri` |
| `get-prompt` | Get a prompt | `prompt`, `arguments` |

### Expectations

```json
{
  "expect": {
    "isError": false,        // Check if tool returned error
    "minTools": 5,           // Minimum tool count
    "contains": "success"    // Response contains string
  }
}
```

## Commands

```bash
# Run full test suite
docker compose run --rm tests run-tests

# List tools on server
docker compose run --rm tests list-tools

# Test specific tool
docker compose run --rm tests test-tool <tool-name> [key=value ...]

# Interactive MCP Inspector
docker compose up inspector
# Then open http://localhost:6274

# Shell access for debugging
docker compose run --rm tests shell
```

## Test Results

Results are written to `./results/`:

- `results.json` - Full test results with output
- `summary.json` - Pass/fail counts
- `junit.xml` - JUnit format for CI integration

## GitHub Actions Integration

Copy `.github/workflows/mcp-tests.yml` to your repo.

Required secrets:
- `MCP_SERVER_URL` - Your MCP server endpoint
- `MCP_ACCESS_TOKEN` - OAuth access token

Optional secrets:
- `MCP_REFRESH_TOKEN` - OAuth refresh token
- `CF_ACCESS_CLIENT_ID` - Cloudflare service token ID
- `CF_ACCESS_CLIENT_SECRET` - Cloudflare service token secret

## Multi-Server Testing

Test multiple MCP servers by extending the matrix in the GitHub Actions workflow:

```yaml
strategy:
  matrix:
    server:
      - name: basicmemory
        url_secret: BASICMEMORY_URL
        token_secret: BASICMEMORY_TOKEN
      - name: docker-mcp
        url_secret: DOCKER_MCP_URL
        token_secret: DOCKER_MCP_TOKEN
      - name: monica-mcp
        url_secret: MONICA_MCP_URL
        token_secret: MONICA_MCP_TOKEN
```

## Token Refresh

OAuth tokens expire. Options for handling:

1. **Long-lived tokens**: Some OAuth providers allow configuring longer expiration
2. **Refresh tokens**: If your server supports refresh, store `MCP_REFRESH_TOKEN`
3. **Service tokens**: Cloudflare service tokens don't expire (until revoked)
4. **Periodic re-auth**: Run `obtain-tokens.sh` periodically and update secrets

## Troubleshooting

### Connection refused
- Check `MCP_SERVER_URL` is correct
- Verify server is running and accessible
- Check Cloudflare tunnel status if using tunnels

### 401 Unauthorized
- Token may be expired - re-run `obtain-tokens.sh`
- Check token is correctly set in environment
- Verify Cloudflare Access policies allow your auth method

### SSL/TLS errors
- Ensure URL uses `https://`
- Check certificate validity
- For self-signed certs, you may need to add CA cert to container

### Timeout errors
- Increase `TEST_TIMEOUT` environment variable
- Check server response times
- Verify network connectivity

## Development

```bash
# Build locally
docker build -t mcp-test-harness:dev .

# Run with local changes
docker run --rm \
  -e MCP_SERVER_URL \
  -e MCP_ACCESS_TOKEN \
  -v $(pwd)/scripts:/app/scripts:ro \
  -v $(pwd)/tests:/app/tests:ro \
  mcp-test-harness:dev run-tests
```

## License

MIT
