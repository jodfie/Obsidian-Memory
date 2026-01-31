# MCP Server Implementation Audit Report

**Date:** 2026-01-21
**Project:** Obsidian-Memory
**Auditor:** Claude Code

## Executive Summary

The current Obsidian-Memory MCP implementation uses a **FastAPI proxy + Bun MCP server** architecture that differs significantly from the recommended **Cloudflare Workers + McpAgent** pattern. While functional for local development, this architecture has several gaps that prevent successful OAuth authentication with Claude.ai.

### Critical Issues

1. **Incomplete SSE transport** - Message endpoint returns placeholder, doesn't route to MCP handlers
2. **No OAuth state persistence** - State lost on server restart, causing "state mismatch" errors
3. **Missing CSRF protection** - Vulnerable to OAuth redirect attacks
4. **Dual OAuth handling** - Both MCP server and FastAPI proxy implement OAuth, causing confusion

---

## Architecture Comparison

### Current Implementation

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Claude.ai  │────▶│ Cloudflare Tunnel│────▶│ FastAPI Proxy  │
└─────────────┘     └──────────────────┘     │ (mcp.py)       │
                                              │ - /authorize   │
                                              │ - /token       │
                                              │ - /mcp/sse     │
                                              └───────┬────────┘
                                                      │
                                              ┌───────▼────────┐
                                              │ Bun MCP Server │
                                              │ (sse.ts)       │
                                              │ - /sse         │
                                              │ - /message     │
                                              │ - /authorize   │ ◀── DUPLICATE!
                                              │ - /token       │ ◀── DUPLICATE!
                                              └────────────────┘
```

### Recommended Pattern (Cloudflare Workers)

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│  Claude.ai  │────▶│ Cloudflare Worker with McpAgent          │
└─────────────┘     │                                          │
                    │  ┌─────────────────┐  ┌───────────────┐  │
                    │  │ OAuthProvider   │  │ Durable Object│  │
                    │  │ - /authorize    │  │ (McpAgent)    │  │
                    │  │ - /token        │  │ - /sse        │  │
                    │  │ - /register     │  │ - /mcp        │  │
                    │  └─────────────────┘  └───────────────┘  │
                    │                                          │
                    │  ┌─────────────────┐                     │
                    │  │ KV (OAUTH_KV)   │                     │
                    │  │ - state tokens  │                     │
                    │  │ - client regs   │                     │
                    │  └─────────────────┘                     │
                    └──────────────────────────────────────────┘
```

---

## Detailed Gap Analysis

### 1. SSE Transport Implementation

**Current State (`mcp-server/src/transport/sse.ts:145-172`):**
```typescript
// Message endpoint - client sends messages here
if (url.pathname === messagePath && req.method === 'POST') {
  // ...
  // Note: This is a simplified implementation
  // A full implementation would need to properly integrate with the Server's
  // internal request routing mechanism.
  const response: JSONRPCResponse = {
    jsonrpc: '2.0',
    id: body.id ?? undefined,
    result: {
      message: 'SSE transport is active. Full MCP protocol integration requires custom Transport implementation.',
      transport: 'sse',
      // ...
    },
  };
```

**Problem:** The message endpoint doesn't actually process MCP requests - it returns a placeholder message. This means tools won't work over SSE.

**Reference Pattern (`@modelcontextprotocol/sdk`):**
The SDK expects a custom `Transport` class that properly routes requests to the Server's handlers.

**Fix Required:**
- Implement proper `Transport` class that connects the HTTP endpoints to the MCP Server's request handlers
- Or use `McpAgent.serve('/mcp')` and `McpAgent.serveSSE('/sse')` from the Cloudflare agents SDK

---

### 2. OAuth State Management

**Current State:**
- OAuth state parameters passed directly to Cloudflare Access
- No local storage of state for validation
- State is only validated by Cloudflare, not by the MCP server

**Reference Pattern (`oauth-setup.md:160-235`):**
```typescript
// Create state before redirecting to upstream provider
async function createOAuthState(oauthReqInfo: AuthRequest, kv: KVNamespace) {
  const stateToken = crypto.randomUUID();
  await kv.put(`oauth:state:${stateToken}`, JSON.stringify(oauthReqInfo), {
    expirationTtl: 600
  });
  return { stateToken };
}

// Bind state to browser session via hashed cookie
async function bindStateToSession(stateToken: string) {
  const hashBuffer = await crypto.subtle.digest("SHA-256", encoder.encode(stateToken));
  return {
    setCookie: `__Host-CONSENTED_STATE=${hashHex}; HttpOnly; Secure; Path=/; SameSite=Lax; Max-Age=600`
  };
}
```

**Fix Required:**
- Add KV namespace binding for state storage
- Store state token with expiration before redirect
- Bind state to session with secure cookie
- Validate state on callback

---

### 3. CSRF Protection

**Current State:**
- No CSRF token generation
- No secure cookie validation
- Consent flow bypassed (direct redirect to Cloudflare)

**Reference Pattern (`oauth-setup.md:55-88`):**
```typescript
function generateCSRFProtection() {
  const token = crypto.randomUUID();
  const setCookie = `__Host-CSRF_TOKEN=${token}; HttpOnly; Secure; Path=/; SameSite=Lax; Max-Age=600`;
  return { token, setCookie };
}

function validateCSRFToken(formData: FormData, request: Request) {
  const tokenFromForm = formData.get("csrf_token");
  const tokenFromCookie = request.headers.get("Cookie")
    ?.split(";")
    .find(c => c.trim().startsWith("__Host-CSRF_TOKEN="))
    ?.split("=")[1];

  if (tokenFromForm !== tokenFromCookie) {
    throw new Error("CSRF token mismatch");
  }
}
```

**Fix Required:**
- Generate CSRF token and set as `__Host-CSRF_TOKEN` cookie
- Include token in hidden form field
- Validate token match before processing consent

---

### 4. Duplicate OAuth Handlers

**Current State:**
Two sets of OAuth endpoints exist:
1. FastAPI proxy (`backend/app/api/mcp.py:169-314`) - `/authorize`, `/token`, `/.well-known/*`
2. Bun MCP server (`mcp-server/src/transport/sse.ts:241-379`) - Same endpoints

**Problem:**
- Confusion about which handlers are used
- Cloudflare Tunnel routes determine which gets called
- Potential for inconsistent behavior

**Fix Required:**
- Remove OAuth handlers from one location
- Recommended: Keep in FastAPI proxy since it's the public-facing service

---

### 5. JWT Audience Validation

**Current State (`cloudflare_access.py:130-134`):**
```python
oauth_client_id = getattr(settings, 'cloudflare_oauth_client_id', None)
valid_audiences = [team_domain]
if oauth_client_id:
    valid_audiences.append(oauth_client_id)
```

**Issue:** The OAuth client ID needs to be properly configured as an environment variable. Currently checking both team_domain and client_id as audiences, which is correct.

**Status:** Partially correct, but needs verification that `cloudflare_oauth_client_id` is set in production.

---

### 6. Content Security Policy

**Current State:**
- No CSP headers on responses
- No nonce-based script security

**Reference Pattern (`oauth-setup.md:130-154`):**
```typescript
function buildSecurityHeaders(setCookie: string, nonce?: string) {
  const cspDirectives = [
    "default-src 'none'",
    "script-src 'self'" + (nonce ? ` 'nonce-${nonce}'` : ""),
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' https:",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");

  return {
    "Content-Security-Policy": cspDirectives,
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
  };
}
```

**Fix Required:**
- Add CSP headers to all OAuth-related responses
- Use nonces for any inline scripts

---

## Recommended Migration Path

### Option A: Fix Current Architecture (Minimal Changes)

1. **Fix SSE message routing**
   - Implement proper MCP Transport class in `sse.ts`
   - Route POST `/message` requests to Server handlers

2. **Add state persistence**
   - Use Redis or file-based storage for OAuth state
   - Implement state validation on callback

3. **Remove duplicate OAuth handlers**
   - Delete OAuth endpoints from `sse.ts`
   - Keep FastAPI proxy as sole OAuth handler

4. **Add CSRF protection**
   - Generate CSRF token on authorize
   - Validate on token exchange

### Option B: Migrate to Cloudflare Workers (Recommended)

1. **Create new Cloudflare Worker project**
   ```bash
   npm create cloudflare -- obsidian-mcp \
     --template=cloudflare/ai/demos/remote-mcp-github-oauth
   ```

2. **Implement McpAgent with existing tools**
   ```typescript
   export class ObsidianMCP extends McpAgent<Env, {}, Props> {
     server = new McpServer({ name: "obsidian-memory", version: "1.0.0" });

     async init() {
       // Register mem_read, mem_write, etc.
       this.server.tool("mem_read", schema, handler);
     }
   }
   ```

3. **Configure OAuthProvider**
   ```typescript
   export default new OAuthProvider({
     apiHandlers: {
       '/sse': ObsidianMCP.serveSSE('/sse'),
       '/mcp': ObsidianMCP.serve('/mcp'),
     },
     authorizeEndpoint: "/authorize",
     tokenEndpoint: "/token",
     defaultHandler: CloudflareAccessHandler,
   });
   ```

4. **Configure wrangler.toml**
   ```toml
   [durable_objects]
   bindings = [{ name = "MCP", class_name = "ObsidianMCP" }]

   [[kv_namespaces]]
   binding = "OAUTH_KV"
   id = "xxx"

   [[migrations]]
   tag = "v1"
   new_classes = ["ObsidianMCP"]
   ```

5. **Deploy and update DNS**
   - Deploy Worker: `wrangler deploy`
   - Update mcp.redleif.dev to point to Worker

---

## Immediate Action Items

### Priority 1: Fix the "error connecting to MCP server" issue

The root cause is likely the incomplete SSE transport. When Claude.ai sends tool requests to `/mcp/message`, it receives the placeholder response instead of actual tool results.

**Quick Fix:**
1. Edit `mcp-server/src/transport/sse.ts`
2. Connect the POST `/message` handler to the MCP Server's request processing
3. Return actual tool results instead of placeholder

### Priority 2: Verify OAuth configuration

```bash
# Test OAuth endpoints
curl -I https://mcp.redleif.dev/.well-known/oauth-authorization-server
curl -I https://mcp.redleif.dev/authorize?response_type=code&client_id=...&redirect_uri=...
```

### Priority 3: Check server logs during Claude.ai connection

```bash
# Watch MCP server logs
docker logs -f memory-mcp-dev

# Watch FastAPI logs
docker logs -f memory
```

---

## Environment Variables Required

```env
# Current (working)
CLOUDFLARE_ACCESS_ENABLED=true
CLOUDFLARE_ACCESS_TEAM_DOMAIN=redleif.cloudflareaccess.com

# Needed for OAuth
CLOUDFLARE_OAUTH_CLIENT_ID=<from BWS>
CLOUDFLARE_OAUTH_CLIENT_SECRET=<from BWS>

# For Cloudflare Workers migration
WRANGLER_HYPERDRIVE_LOCAL_CONNECTION_STRING_HYPERDRIVE=<postgres connection>
```

---

## References

- [MCP Authorization Spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)
- [Cloudflare MCP Server Template](https://github.com/cloudflare/ai/tree/main/demos/remote-mcp-github-oauth)
- [workers-oauth-provider Documentation](https://github.com/cloudflare/workers-oauth-provider)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)
