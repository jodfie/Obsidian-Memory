# Supabase OAuth Setup for Claude.ai MCP

This guide explains how to configure Supabase as an OAuth 2.0 provider for Claude.ai to access your Obsidian-Memory MCP server.

## Prerequisites

- Supabase project created (you have: https://uspohhdhzwigalsrugqc.supabase.co)
- Obsidian-Memory backend deployed
- Access to Supabase dashboard

## Step 1: Enable OAuth in Supabase

1. Go to your Supabase dashboard: https://supabase.com/dashboard
2. Navigate to **Authentication** → **Providers**
3. Enable the providers you want to use for user authentication (e.g., Google, GitHub)
   - For Claude.ai integration, you'll primarily use JWT validation, not social auth

## Step 2: Configure OAuth Application

### Option A: Using Supabase Auth (Recommended)

Supabase provides built-in OAuth 2.0 endpoints:

**Authorization endpoint:**
```
https://uspohhdhzwigalsrugqc.supabase.co/auth/v1/authorize
```

**Token endpoint:**
```
https://uspohhdhzwigalsrugqc.supabase.co/auth/v1/token
```

**JWKS endpoint (for token validation):**
```
https://uspohhdhzwigalsrugqc.supabase.co/auth/v1/.well-known/jwks.json
```

### Option B: Create Custom OAuth Application

If you need more control:

1. Go to **Authentication** → **Settings**
2. Under **OAuth Providers**, click **Add Provider**
3. Configure:
   - **Provider Name**: Claude.ai MCP
   - **Client ID**: (auto-generated)
   - **Redirect URLs**: Add Claude.ai callback URLs
     - `https://claude.ai/api/auth/callback`
     - Any other Claude.ai OAuth redirect URLs

## Step 3: Get OAuth Credentials

1. In Supabase dashboard, go to **Settings** → **API**
2. Copy the following:
   - **Project URL**: `https://uspohhdhzwigalsrugqc.supabase.co`
   - **anon (public) key**: Already stored in Phase secrets
   - **service_role key**: Already stored in Phase secrets (used for server-side validation)

## Step 4: Configure Claude.ai MCP Integration

When adding your MCP server to Claude.ai:

1. **MCP Server URL**: `https://memory.redleif.dev/mcp`

2. **OAuth Configuration**:
   - **Authorization URL**: `https://uspohhdhzwigalsrugqc.supabase.co/auth/v1/authorize`
   - **Token URL**: `https://uspohhdhzwigalsrugqc.supabase.co/auth/v1/token`
   - **Client ID**: (from Supabase dashboard)
   - **Client Secret**: (from Supabase dashboard)
   - **Scopes**: `openid profile email` (or as configured)

## Step 5: Test Authentication

### Test with curl:

```bash
# Get an access token (you'll need to do the OAuth flow manually or use Supabase client)
TOKEN="your-access-token"

# Test MCP endpoint
curl -X POST https://memory.redleif.dev/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1}'
```

### Expected Response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-03-26",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "obsidian-memory",
      "version": "0.2.0"
    }
  }
}
```

## How It Works

```
┌─────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Claude.ai  │────────>│   Supabase   │────────>│ Obsidian-Memory │
│             │  OAuth  │   Auth API   │  JWT    │   Backend       │
└─────────────┘         └──────────────┘         └─────────────────┘
                                                          │
                                                          v
                                                  ┌──────────────┐
                                                  │ MCP Server   │
                                                  └──────────────┘
```

1. **Claude.ai initiates OAuth flow** with Supabase
2. **User authorizes** in Supabase UI
3. **Supabase issues JWT access token** to Claude.ai
4. **Claude.ai calls MCP endpoint** with `Authorization: Bearer <token>`
5. **Backend validates JWT**:
   - Fetches Supabase JWKS (public keys)
   - Verifies signature, expiration, issuer
   - Extracts user identity
6. **MCP server processes request** (no auth logic needed)

## Environment Variables

Already configured in `docker-compose.prod.yml`:

```yaml
environment:
  - SUPABASE_AUTH_ENABLED=true
  - SUPABASE_URL=${SUPABASE_URL}  # https://uspohhdhzwigalsrugqc.supabase.co
```

Note: `SUPABASE_JWT_SECRET` is optional - we use JWKS (public key) validation instead.

## Advantages Over Cloudflare Access

✅ **Simpler setup** - No separate Access application configuration  
✅ **Better integration** - Supabase is already in your stack  
✅ **Standard OAuth 2.0** - Well-documented, widely supported  
✅ **Flexible scopes** - Fine-grained access control  
✅ **User management** - Built-in user database and admin panel  

## Troubleshooting

### "Invalid token" errors:

- Check that `SUPABASE_URL` matches your project URL
- Verify token hasn't expired (default: 1 hour)
- Ensure JWKS endpoint is accessible

### "Failed to fetch public keys":

- Check network connectivity to Supabase
- Verify `SUPABASE_URL` is correct
- Check firewall rules

### Claude.ai can't connect:

- Verify redirect URLs are configured in Supabase
- Check that MCP endpoint is accessible: `https://memory.redleif.dev/mcp`
- Test with curl first to isolate OAuth vs MCP issues

## Next Steps

1. Configure OAuth app in Supabase dashboard
2. Add redirect URLs for Claude.ai
3. Test OAuth flow with curl/Postman
4. Add MCP server to Claude.ai with OAuth credentials
5. Verify tools are accessible in Claude.ai

## Security Notes

- JWT tokens are validated using Supabase's public keys (RS256)
- Tokens expire after configured TTL (default: 1 hour)
- Backend caches JWKS for 1 hour to reduce latency
- Internal Docker network requests bypass OAuth (trusted network)
- Health/docs endpoints are public (no auth required)
