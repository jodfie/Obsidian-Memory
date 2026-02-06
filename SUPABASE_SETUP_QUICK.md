# Supabase OAuth Quick Setup (Copy & Paste)

✅ **Backend is already configured** - just need to update Supabase dashboard

## What I've Done Already:

✅ Set up Supabase auth middleware in backend  
✅ Configured GitHub secrets for CI/CD  
✅ Updated docker-compose with Supabase env vars  
✅ Disabled Cloudflare Access (Supabase is primary)  

## What You Need to Do (5 minutes):

### Step 1: Open Supabase Dashboard

Go to: **https://supabase.com/dashboard/project/uspohhdhzwigalsrugqc**

### Step 2: Add Redirect URL for Claude.ai

1. Click **Authentication** (left sidebar)
2. Click **URL Configuration**
3. Under **Redirect URLs**, click **Add URL**
4. **Copy and paste this:**
   ```
   https://claude.ai/api/auth/callback
   ```
5. Click **Save**

### Step 3: Get Your OAuth Credentials

Your OAuth endpoints (already configured in backend, use these for Claude.ai):

**Authorization Endpoint:**
```
https://uspohhdhzwigalsrugqc.supabase.co/auth/v1/authorize
```

**Token Endpoint:**
```
https://uspohhdhzwigalsrugqc.supabase.co/auth/v1/token
```

**Client ID (anon key):**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVzcG9oaGRoendpZ2Fsc3J1Z3FjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAzMDM4NDEsImV4cCI6MjA4NTg3OTg0MX0.TqEZBvZmHqO5Hlc_jZvtJx2qA9gIDg8OE_w23UYEpb4
```

**Client Secret:**
```
(Leave blank or contact Supabase support if Claude.ai requires it)
```

**Scopes:**
```
openid profile email
```

### Step 4: Configure Claude.ai MCP Connection

When adding MCP server in Claude.ai, use these exact values:

**MCP Server URL:**
```
https://memory.redleif.dev/mcp
```

**OAuth Configuration:**
- Authorization URL: `https://uspohhdhzwigalsrugqc.supabase.co/auth/v1/authorize`
- Token URL: `https://uspohhdhzwigalsrugqc.supabase.co/auth/v1/token`
- Client ID: (copy the anon key above)
- Client Secret: (leave blank)
- Scopes: `openid profile email`

---

## That's It!

Once you add the redirect URL in Supabase and configure Claude.ai:
1. Claude.ai will redirect to Supabase for OAuth
2. You'll authorize once
3. Supabase issues a JWT token
4. Backend validates the token
5. MCP tools become available in Claude.ai

## Alternative: Skip OAuth (Temporary Testing)

If you want to test without OAuth first, you can temporarily disable auth:

In your `.env` or docker-compose:
```bash
SUPABASE_AUTH_ENABLED=false
```

But this is **NOT recommended for production** - only for local testing.

---

**Current Status:**
- ✅ Backend configured
- ✅ GitHub secrets set
- ✅ Docker compose updated
- ⏳ Waiting for: Supabase redirect URL + Claude.ai config

**Build Status:** Check Discord for deployment notifications
