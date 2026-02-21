# Cloudflare Access Setup - What's Left

## ✅ Completed (Code Implementation)

1. **JWT Verification Implementation**
   - ✅ Added `pyjwt[cryptography]` dependency
   - ✅ Implemented proper JWT signature verification using Cloudflare's public keys
   - ✅ Added public key caching (1 hour TTL) to reduce API calls
   - ✅ Validates JWT signature, expiration, issuer, and audience
   - ✅ Extracts user identity from JWT claims

2. **Middleware Configuration**
   - ✅ Cloudflare Access middleware integrated in FastAPI
   - ✅ Skips auth for `/health`, `/docs`, `/openapi.json`, `/redoc`
   - ✅ All other endpoints require valid Cloudflare Access JWT

3. **Docker Configuration**
   - ✅ Environment variables configured in docker-compose files
   - ✅ Traefik labels configured for header forwarding

## 🔧 Remaining Steps (Manual Configuration)

### 1. Cloudflare Zero Trust Configuration (REQUIRED)

**This is the most critical step - without it, Cloudflare Access won't protect your domain.**

1. **Go to Cloudflare Zero Trust Dashboard**
   - URL: https://one.dash.cloudflare.com
   - Navigate to: **Access** → **Applications**

2. **Create Application**
   - Click **Add an application**
   - Select **Self-hosted**
   - Application name: `Obsidian-Memory Dev` (or `Obsidian-Memory Prod`)
   - Application domain: `memory-dev.example.com` (dev) or `memory.example.com` (prod)

3. **Configure Access Policy**
   - Click **Add a policy**
   - Policy name: `Allow authenticated users`
   - Action: **Allow**
   - Include:
     - Email domain: `@example.com` (or your domain)
     - Or specific email addresses
   - Save policy

4. **Save Application**

**Without this configuration, requests will NOT be protected by Cloudflare Access.**

### 2. DNS Configuration

Ensure your domain is properly configured:

- [ ] Domain `memory-dev.example.com` (dev) added to Cloudflare DNS
- [ ] Domain `memory.example.com` (prod) added to Cloudflare DNS
- [ ] DNS proxy enabled (orange cloud ☁️) - **CRITICAL**
- [ ] DNS points to your server/Traefik or Cloudflare Tunnel

**To check:**
```bash
# DNS should show Cloudflare IPs when proxied
dig memory-dev.example.com
# Should show Cloudflare IPs (not your server IP)
```

### 3. Cloudflare Tunnel (if using)

If you're using Cloudflare Tunnel instead of direct connection:

- [ ] Cloudflare Tunnel is running (cloudflared daemon)
- [ ] Route configured: `memory-dev.example.com` → `http://traefik:80`
- [ ] Route configured: `memory.example.com` → `http://traefik:80`
- [ ] Access application is linked to the tunnel route

**Tunnel configuration example:**
```yaml
# config.yml
tunnel: <tunnel-id>
credentials-file: /path/to/credentials.json

ingress:
  - hostname: memory-dev.example.com
    service: http://traefik:80
  - hostname: memory.example.com
    service: http://traefik:80
  - service: http_status:404
```

### 4. Environment Variables

**Using Helper Script (Easiest):**

Run the interactive helper script:

```bash
./scripts/configure-cloudflare-access.sh
```

This script will:
- Check if Infisical CLI is configured
- Prompt for your Cloudflare Access team domain
- Set secrets for dev and/or prod environments
- Optionally export to `.env` files

**Using Infisical CLI Directly:**

If you prefer to set secrets manually:

```bash
# Set Cloudflare Access secrets for dev environment
infisical-cli secrets set CLOUDFLARE_ACCESS_ENABLED=true --env=dev
infisical-cli secrets set CLOUDFLARE_ACCESS_TEAM_DOMAIN=your-team.cloudflareaccess.com --env=dev

# Set Cloudflare Access secrets for prod environment
infisical-cli secrets set CLOUDFLARE_ACCESS_ENABLED=true --env=prod
infisical-cli secrets set CLOUDFLARE_ACCESS_TEAM_DOMAIN=your-team.cloudflareaccess.com --env=prod

# Export to .env files (optional, for local development)
infisical-cli export --format=dotenv --env=dev > .env.dev
infisical-cli export --format=dotenv --env=prod > .env.prod
```

**Manual Configuration (Alternative):**

If not using Infisical, set these in your `.env.dev` and `.env.prod` files:

**Development (.env.dev):**
```bash
CLOUDFLARE_ACCESS_ENABLED=true
CLOUDFLARE_ACCESS_TEAM_DOMAIN=your-team.cloudflareaccess.com
```

**Production (.env.prod):**
```bash
CLOUDFLARE_ACCESS_ENABLED=true
CLOUDFLARE_ACCESS_TEAM_DOMAIN=your-team.cloudflareaccess.com
```

**Important:** Replace `your-team.cloudflareaccess.com` with your actual Cloudflare Access team domain. You can find this in:
- Cloudflare Zero Trust Dashboard → Access → Applications → Your Application
- It's typically: `<your-team-name>.cloudflareaccess.com`

### 5. Identity Provider Configuration (if not already done)

If you haven't configured an identity provider:

1. **Go to Access** → **Authentication**
2. **Add Identity Provider**:
   - Google OAuth
   - GitHub OAuth
   - Microsoft OAuth
   - Or custom OAuth 2.0 provider
3. **Configure** with your OAuth credentials
4. **Link to Access Application** (done in step 1)

### 6. Deploy and Test

1. **Deploy the application:**
   ```bash
   # Development
   make dev
   
   # Production
   make prod
   ```

2. **Test unauthenticated access:**
   ```bash
   curl -I https://memory-dev.example.com/
   # Should return: 302 Redirect to Cloudflare Access login
   # Or: 401 if CF-Access-JWT header missing
   ```

3. **Test authenticated access:**
   - Open browser: https://memory-dev.example.com/
   - Should redirect to Cloudflare Access login
   - Authenticate with your identity provider
   - Should redirect back to application

4. **Test health endpoint (public):**
   ```bash
   curl https://memory-dev.example.com/health
   # Should return: 200 OK (health check is public)
   ```

5. **Check application logs:**
   ```bash
   make logs-dev
   # Look for JWT verification messages
   ```

## Verification Checklist

- [ ] Cloudflare Zero Trust application created for domain
- [ ] Access policy configured with allowed users
- [ ] DNS configured and proxied (orange cloud)
- [ ] Cloudflare Tunnel running (if using tunnel)
- [ ] Environment variables set: `CLOUDFLARE_ACCESS_ENABLED=true`
- [ ] Environment variables set: `CLOUDFLARE_ACCESS_TEAM_DOMAIN=...`
- [ ] Application deployed with Cloudflare Access enabled
- [ ] Test: Unauthenticated request redirects to login
- [ ] Test: Authenticated request works with JWT
- [ ] Test: Health endpoint is accessible without auth

## Troubleshooting

### "No redirect to Cloudflare Access login"

**Problem**: Domain not configured in Cloudflare Access.

**Solution**: 
1. Verify application exists in Cloudflare Zero Trust
2. Check application domain matches exactly (no trailing slash)
3. Verify DNS is proxied (orange cloud)

### "CF-Access-JWT header missing"

**Problem**: Request not going through Cloudflare Access.

**Solutions**:
1. Verify Cloudflare Access application is active
2. Check DNS is proxied (orange cloud)
3. Verify request is going through Cloudflare (check DNS resolution)
4. If using tunnel, verify tunnel is running and route is configured

### "Invalid Cloudflare Access token" or "JWT verification failed"

**Problem**: JWT validation fails in application.

**Solutions**:
1. Check `CLOUDFLARE_ACCESS_TEAM_DOMAIN` matches your Cloudflare Access team domain exactly
2. Verify JWT hasn't expired (tokens expire after session duration)
3. Check application logs for detailed error messages
4. Verify public keys are being fetched correctly (check logs)

### "Failed to fetch Cloudflare Access public keys"

**Problem**: Cannot fetch JWKS from Cloudflare.

**Solutions**:
1. Verify `CLOUDFLARE_ACCESS_TEAM_DOMAIN` is correct
2. Check network connectivity to Cloudflare
3. Verify team domain format: `<team-name>.cloudflareaccess.com`
4. Check Cloudflare Zero Trust dashboard for any service issues

## Next Steps After Setup

1. **Monitor logs** for JWT verification
2. **Test with different users** to verify access policies
3. **Review Cloudflare Access logs** in Zero Trust dashboard
4. **Set up alerts** for authentication failures (optional)
5. **Document your team domain** for future reference

## Summary

**Code is complete** ✅ - The application now properly verifies Cloudflare Access JWTs with signature validation.

**What you need to do:**
1. Configure Cloudflare Zero Trust application (most important)
2. Set environment variables
3. Deploy and test

The code will automatically:
- Fetch public keys from Cloudflare
- Verify JWT signatures
- Validate expiration, issuer, and audience
- Extract user identity from tokens
