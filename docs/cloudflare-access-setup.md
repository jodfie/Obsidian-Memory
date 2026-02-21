# Cloudflare Access Setup for memory-dev.example.com

This guide explains how to configure Cloudflare Access to protect `memory-dev.example.com` behind OAuth 2.0 authentication.

## Overview

Cloudflare Access provides OAuth 2.0 authentication at the Cloudflare edge, before requests reach your application. The flow is:

1. User requests `https://memory-dev.example.com`
2. Cloudflare Access intercepts (if not authenticated)
3. User authenticates via OAuth 2.0 (Google, GitHub, etc.)
4. Cloudflare injects `CF-Access-JWT` header
5. Request forwarded to Traefik → FastAPI
6. FastAPI middleware validates JWT

## Prerequisites

- Domain `memory-dev.example.com` must be:
  - Added to Cloudflare DNS
  - Proxied through Cloudflare (orange cloud enabled)
  - Accessible via Cloudflare Tunnel or direct connection

## Step 1: Configure Cloudflare Access Application

1. **Go to Cloudflare Zero Trust Dashboard**
   - Navigate to: https://one.dash.cloudflare.com
   - Or: https://dash.cloudflare.com → Zero Trust

2. **Create Application**
   - Go to **Access** → **Applications**
   - Click **Add an application**
   - Select **Self-hosted**

3. **Application Configuration**
   ```
   Application name: Obsidian-Memory Dev
   Session duration: 24 hours (or as needed)
   ```

4. **Application Domain**
   ```
   Application domain: memory-dev.example.com
   ```

5. **Add Policy**
   - Click **Add a policy**
   - **Policy name**: `Allow authenticated users`
   - **Action**: Allow
   - **Include**:
     - Email domain: `@example.com` (or your domain)
     - Or specific emails
   - **Save policy**

6. **Save Application**

## Step 2: Configure Identity Provider (if not already done)

1. **Go to Access** → **Authentication**
2. **Add Identity Provider**:
   - Google
   - GitHub
   - Microsoft
   - Or custom OAuth 2.0 provider
3. **Configure** with your OAuth credentials

## Step 3: Verify Traefik Configuration

Traefik automatically forwards Cloudflare Access headers. Verify your Traefik configuration includes:

```yaml
# Traefik should forward these headers automatically:
# - CF-Access-JWT
# - CF-Access-JWT-Assertion
# - CF-Access-JWT-Assertion-Expiry
```

The docker-compose labels already include header forwarding middleware.

## Step 4: Configure Environment Variables

### Using Infisical CLI (Recommended)

```bash
# Set secrets in Infisical
infisical-cli secrets set CLOUDFLARE_ACCESS_ENABLED=true
infisical-cli secrets set CLOUDFLARE_ACCESS_TEAM_DOMAIN=your-team.cloudflareaccess.com

# Export to .env.dev
infisical-cli export --format=dotenv --env=dev > .env.dev
```

### Manual Configuration

Edit `.env.dev`:
```bash
CLOUDFLARE_ACCESS_ENABLED=true
CLOUDFLARE_ACCESS_TEAM_DOMAIN=your-team.cloudflareaccess.com
```

## Step 5: Deploy and Test

```bash
# Deploy development environment
make dev

# Test access
curl -I https://memory-dev.example.com/health
# Should return 200 (health check is public)

curl -I https://memory-dev.example.com/
# Should redirect to Cloudflare Access login if not authenticated
```

## Step 6: Verify JWT Validation

The FastAPI middleware validates the JWT. To improve security, implement proper JWT verification:

1. **Install PyJWT**:
   ```bash
   pip install pyjwt cryptography
   ```

2. **Update middleware** to verify JWT signature using Cloudflare's public keys:
   ```python
   # Fetch public keys from:
   # https://<team-domain>.cloudflareaccess.com/cdn-cgi/access/certs
   ```

## Troubleshooting

### "Cloudflare Access JWT token required"

**Problem**: Request doesn't have `CF-Access-JWT` header.

**Solutions**:
1. Verify domain is configured in Cloudflare Access
2. Check Cloudflare DNS is proxied (orange cloud)
3. Verify Cloudflare Tunnel is running (if using tunnel)
4. Check Traefik is forwarding headers

### "Invalid Cloudflare Access token"

**Problem**: JWT validation fails.

**Solutions**:
1. Check `CLOUDFLARE_ACCESS_TEAM_DOMAIN` is correct
2. Verify JWT hasn't expired
3. Check middleware is properly configured
4. Review Cloudflare Access logs in Zero Trust dashboard

### Can't access even after authentication

**Problem**: Authenticated but still getting 401.

**Solutions**:
1. Check access policy allows your email/domain
2. Verify session hasn't expired
3. Check application domain matches exactly
4. Review Cloudflare Access logs

## Using Infisical for Secrets

If you have Infisical CLI installed:

```bash
# List available secrets
infisical-cli secrets

# Get Cloudflare Access config
infisical-cli secrets get CLOUDFLARE_ACCESS_ENABLED
infisical-cli secrets get CLOUDFLARE_ACCESS_TEAM_DOMAIN

# Export all secrets for dev environment
infisical-cli export --format=dotenv --env=dev > .env.dev

# Run docker-compose with secrets
infisical-cli run -- docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up -d
```

## Security Notes

- Cloudflare Access provides OAuth 2.0 at the edge
- JWT tokens are short-lived (default: 24 hours)
- All requests to protected endpoints require valid JWT
- Health check endpoint (`/health`) is public (by design)
- API docs (`/docs`) are public (by design)

## Next Steps

1. Configure Cloudflare Access application in Zero Trust
2. Set up identity provider (Google, GitHub, etc.)
3. Test authentication flow
4. Deploy with `CLOUDFLARE_ACCESS_ENABLED=true`
5. Verify JWT validation in application logs
