# Authentication Guide

This guide covers authentication setup for Obsidian-Memory API.

## Authentication Methods

Obsidian-Memory supports three authentication methods:

| Method | Use Case | Security Level |
|--------|----------|----------------|
| Bearer Token | Development, simple deployments | Basic |
| Cloudflare Access | Production web deployments | High |
| OAuth 2.1 | Claude.ai MCP integration | High |

## Bearer Token Authentication

Simple token-based authentication for development or single-user deployments.

### Setup

1. Set the environment variables:

```bash
REQUIRE_AUTH=true
API_AUTH_TOKEN=your-secure-token-here
```

2. Include the token in requests:

```bash
curl -H "Authorization: Bearer your-secure-token-here" \
     http://localhost:8000/api/notes
```

### Security Considerations

- Use a strong, randomly generated token (32+ characters)
- Never commit tokens to version control
- Use HTTPS in production
- Consider rotating tokens periodically

## Cloudflare Access (Recommended)

Cloudflare Access provides zero-trust authentication with SSO integration.

### Prerequisites

- Cloudflare account with Access enabled
- Domain proxied through Cloudflare
- Access application configured

### Step 1: Create Access Application

1. Go to Cloudflare Dashboard > Zero Trust > Access > Applications
2. Click "Add an application" > Self-hosted
3. Configure:
   - **Application name**: Obsidian-Memory API
   - **Session duration**: 24 hours (adjust as needed)
   - **Application domain**: `api.yourdomain.com`

4. Create an Access Policy:
   - **Policy name**: Allow authorized users
   - **Action**: Allow
   - **Include rules**: Email domain, specific emails, or identity provider groups

5. Note the **Application Audience (AUD)** tag from the application settings

### Step 2: Configure the Backend

Set these environment variables:

```bash
CLOUDFLARE_ACCESS_ENABLED=true
CLOUDFLARE_ACCESS_TEAM_DOMAIN=your-team.cloudflareaccess.com
CLOUDFLARE_ACCESS_AUDIENCE=your-application-aud-tag
```

### Step 3: Test Authentication

1. Access your API through the browser - Cloudflare will redirect to login
2. After authentication, the `CF-Access-JWT` header is automatically included
3. The backend validates the JWT against Cloudflare's public keys

### How It Works

```
Client                 Cloudflare Access              Backend
  |                           |                          |
  |--- Request ------------->|                          |
  |                           |--- Redirect to login -->|
  |                           |<-- User authenticates --|
  |<-- JWT cookie ------------|                          |
  |                           |                          |
  |--- Request + JWT ------->|                          |
  |                           |--- Validate JWT ------->|
  |                           |<-- Valid ----------------|
  |<-- Response -------------|<--------------------------|
```

### Service Tokens

For machine-to-machine communication (e.g., MCP servers):

1. Go to Zero Trust > Access > Service Auth > Service Tokens
2. Create a new service token
3. Use the Client ID and Secret in requests:

```bash
curl -H "CF-Access-Client-Id: your-client-id" \
     -H "CF-Access-Client-Secret: your-client-secret" \
     https://api.yourdomain.com/api/notes
```

## OAuth 2.1 (Claude.ai MCP Integration)

For Claude.ai MCP connector integration, OAuth 2.1 with PKCE provides secure authentication.

### Architecture

```
Claude.ai             OAuth Gateway            Backend API
    |                      |                       |
    |--- Auth request ---->|                       |
    |                      |--- Redirect to IdP -->|
    |                      |<-- Auth code ---------|
    |<-- Access token -----|                       |
    |                      |                       |
    |--- API + token ----->|--- Validate -------->|
    |                      |<-- Response ---------|
    |<-- Response ---------|                       |
```

### OAuth Gateway Setup

The OAuth gateway (`oauth-gateway/`) handles OAuth flows for Claude.ai:

1. Deploy the OAuth gateway alongside the backend
2. Configure the gateway:

```yaml
# oauth-gateway/config.yaml
issuer: https://auth.yourdomain.com
authorization_endpoint: /authorize
token_endpoint: /token
registration_endpoint: /register

# Backend API
resource_server: https://api.yourdomain.com

# Supported scopes
scopes:
  - mcp:tools
  - read:notes
  - write:notes
```

3. Register the gateway with Claude.ai:
   - Authorization URL: `https://auth.yourdomain.com/authorize`
   - Token URL: `https://auth.yourdomain.com/token`
   - Callback URLs:
     - `https://claude.ai/api/mcp/auth_callback`
     - `https://claude.com/api/mcp/auth_callback`

### Required Endpoints

The OAuth gateway must implement:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/.well-known/oauth-authorization-server` | GET | Server metadata |
| `/.well-known/oauth-protected-resource` | GET | Resource metadata |
| `/authorize` | GET | Authorization endpoint |
| `/token` | POST | Token endpoint |
| `/register` | POST | Dynamic client registration |

### Protected Resource Metadata

Backend must serve at `/.well-known/oauth-protected-resource`:

```json
{
  "resource": "https://api.yourdomain.com/mcp",
  "authorization_servers": ["https://auth.yourdomain.com"],
  "scopes_supported": ["mcp:tools", "read:notes", "write:notes"]
}
```

### Token Validation

The backend validates OAuth tokens by:

1. Extracting the Bearer token from `Authorization` header
2. Validating the JWT signature against the IdP's public keys
3. Checking the `aud` claim matches the API URL
4. Verifying required scopes are present
5. Confirming the token hasn't expired

## CORS Configuration

When using browser-based clients, configure CORS:

```bash
CORS_ENABLED=true
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://claude.ai
```

The API exposes these headers for client use:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`
- `Retry-After`
- `Mcp-Session-Id`

## Security Best Practices

### Production Checklist

- [ ] Enable HTTPS/TLS termination
- [ ] Use Cloudflare Access or OAuth for authentication
- [ ] Set strong, unique tokens
- [ ] Enable rate limiting
- [ ] Configure CORS appropriately (not `*` in production)
- [ ] Monitor authentication failures
- [ ] Rotate credentials periodically

### Environment Variable Security

Never hardcode credentials. Use:
- Environment files (`.env`) excluded from version control
- Secret management services (Infisical, Vault, AWS Secrets Manager)
- Container orchestration secrets (Kubernetes secrets, Docker secrets)

### Audit Logging

The API logs authentication events:
- Successful authentications
- Failed authentication attempts
- Token validation errors

Review logs regularly for suspicious activity.

## Troubleshooting

### Common Issues

**401 Unauthorized**
- Check that the authentication header is correctly formatted
- Verify the token/credentials are valid
- Ensure the authentication method is enabled

**403 Forbidden**
- Token is valid but lacks required permissions
- User is not in the allowed access policy
- CORS origin not allowed

**JWT Validation Failed**
- Clock skew between servers (check NTP sync)
- Token has expired
- Wrong audience claim
- Invalid signature (wrong public key)

### Debug Mode

Enable debug logging for authentication:

```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

This logs detailed authentication flow information (excluding sensitive values).
