# Cloudflare Access Requirements for memory-dev.redleif.dev

## Critical: Cloudflare Access Must Be Configured in Cloudflare Zero Trust

**The application middleware only validates JWTs - the actual protection happens at Cloudflare's edge.**

## What Needs to Be Done

### 1. Cloudflare Zero Trust Configuration (REQUIRED)

The domain `memory-dev.redleif.dev` MUST be configured in Cloudflare Zero Trust Access:

1. **Go to Cloudflare Zero Trust Dashboard**
   - URL: https://one.dash.cloudflare.com
   - Navigate to: **Access** → **Applications**

2. **Create Application**
   - Application name: `Obsidian-Memory Dev`
   - Application domain: `memory-dev.redleif.dev`
   - Select **Self-hosted**

3. **Configure Access Policy**
   - Policy name: `Allow authenticated users`
   - Action: **Allow**
   - Include: Your email domain or specific emails
   - Save policy

4. **Save Application**

**Without this configuration, Cloudflare Access will NOT protect the domain.**

### 2. DNS Configuration

Ensure `memory-dev.redleif.dev`:
- ✅ Is added to Cloudflare DNS
- ✅ Has proxy enabled (orange cloud ☁️)
- ✅ Points to your server/Traefik

### 3. Cloudflare Tunnel (if using)

If using Cloudflare Tunnel:
- ✅ Tunnel is running
- ✅ Route configured: `memory-dev.redleif.dev` → `http://traefik:80`
- ✅ Access application is linked to the tunnel route

### 4. Application Configuration

The application is already configured to:
- ✅ Validate `CF-Access-JWT` header
- ✅ Require Cloudflare Access for all endpoints (except `/health`, `/docs`)
- ✅ Extract user identity from JWT

**Environment variables needed:**
```bash
CLOUDFLARE_ACCESS_ENABLED=true
CLOUDFLARE_ACCESS_TEAM_DOMAIN=redleif.cloudflareaccess.com
```

### 5. Traefik Configuration

Traefik automatically forwards Cloudflare Access headers:
- ✅ `CF-Access-JWT` - JWT token
- ✅ `CF-Access-JWT-Assertion` - Additional assertion
- ✅ `X-Forwarded-Proto: https` - Protocol forwarding

## How It Works

```
User Request
    ↓
Cloudflare Edge (DNS + Proxy)
    ↓
Cloudflare Access (OAuth 2.0) ← PROTECTION HAPPENS HERE
    ↓
Injects CF-Access-JWT header
    ↓
Cloudflare Tunnel (if used)
    ↓
Traefik (forwards headers)
    ↓
FastAPI Backend (validates JWT)
    ↓
Application Logic
```

## Testing

### Before Cloudflare Access is Configured:
```bash
curl https://memory-dev.redleif.dev/
# Returns: 200 OK (no protection)
```

### After Cloudflare Access is Configured:
```bash
curl https://memory-dev.redleif.dev/
# Returns: 302 Redirect to Cloudflare Access login
# Or: 401 if CF-Access-JWT header missing
```

### With Valid Authentication:
```bash
# After logging in via browser, Cloudflare injects JWT
curl -H "CF-Access-JWT: <token>" https://memory-dev.redleif.dev/
# Returns: 200 OK with application response
```

## Using Infisical for Configuration

If you have Infisical configured:

```bash
# Check if credentials file exists
ls -la ~/.infisical-machine-identity

# If not, create it with:
cat > ~/.infisical-machine-identity <<EOF
INFISICAL_API_URL="https://your-infisical-instance.com/api"
INFISICAL_CLIENT_ID="your-client-id"
INFISICAL_CLIENT_SECRET="your-client-secret"
INFISICAL_PROJECT_ID="your-project-id"
INFISICAL_ENVIRONMENT="dev"
INFISICAL_SECRET_PATH="/"
EOF
chmod 600 ~/.infisical-machine-identity

# Get Cloudflare Access secrets
infisical-cli secrets get CLOUDFLARE_ACCESS_ENABLED
infisical-cli secrets get CLOUDFLARE_ACCESS_TEAM_DOMAIN

# Export to .env.dev
infisical-cli export --format=dotenv --env=dev > .env.dev
```

## Verification Checklist

- [ ] Domain `memory-dev.redleif.dev` added to Cloudflare DNS
- [ ] DNS proxy enabled (orange cloud)
- [ ] Cloudflare Access application created in Zero Trust
- [ ] Access policy configured with allowed users
- [ ] Cloudflare Tunnel running (if using tunnel)
- [ ] Environment variables set: `CLOUDFLARE_ACCESS_ENABLED=true`
- [ ] Environment variables set: `CLOUDFLARE_ACCESS_TEAM_DOMAIN=...`
- [ ] Application deployed with Cloudflare Access enabled
- [ ] Test: Unauthenticated request redirects to login
- [ ] Test: Authenticated request works with JWT

## Troubleshooting

### "No redirect to Cloudflare Access login"

**Problem**: Domain not configured in Cloudflare Access.

**Solution**: Create application in Cloudflare Zero Trust for `memory-dev.redleif.dev`.

### "CF-Access-JWT header missing"

**Problem**: Traefik not forwarding headers or Cloudflare Access not enabled.

**Solutions**:
1. Verify Cloudflare Access application is active
2. Check Traefik is forwarding headers (should be automatic)
3. Verify request is going through Cloudflare (check DNS)

### "Invalid Cloudflare Access token"

**Problem**: JWT validation fails in application.

**Solutions**:
1. Check `CLOUDFLARE_ACCESS_TEAM_DOMAIN` matches your Cloudflare Access team domain
2. Verify JWT hasn't expired
3. Check middleware is properly configured
4. Review application logs for JWT validation errors

## Next Steps

1. **Configure Cloudflare Access in Zero Trust** (REQUIRED)
2. Set environment variables (via Infisical or `.env.dev`)
3. Deploy: `make dev`
4. Test authentication flow
5. Verify JWT validation in logs
