# Quick Infisical Setup

## Option 1: Interactive Script (Easiest)

Run the interactive setup script:

```bash
./scripts/setup-infisical.sh
```

This will prompt you for each credential and create the file automatically.

## Option 2: Manual Setup

Create the credentials file manually:

```bash
cat > ~/.infisical-machine-identity <<'EOF'
INFISICAL_API_URL="https://your-infisical-instance.com/api"
INFISICAL_CLIENT_ID="your-client-id"
INFISICAL_CLIENT_SECRET="your-client-secret"
INFISICAL_PROJECT_ID="your-project-id"
INFISICAL_ENVIRONMENT="dev"
INFISICAL_SECRET_PATH="/"
EOF

chmod 600 ~/.infisical-machine-identity
```

## Option 3: Provide Credentials to Assistant

You can provide the credentials directly, and I'll create the file for you. Just tell me:

1. **INFISICAL_API_URL** - Your Infisical API URL
2. **INFISICAL_CLIENT_ID** - Machine Identity Client ID  
3. **INFISICAL_CLIENT_SECRET** - Machine Identity Client Secret
4. **INFISICAL_PROJECT_ID** - Project ID
5. **INFISICAL_ENVIRONMENT** - Environment (dev/staging/prod)
6. **INFISICAL_SECRET_PATH** - Path (usually "/")

## Where to Find Credentials

### Infisical Cloud (app.infisical.com)

1. **API URL**: `https://app.infisical.com/api`
2. **Machine Identity**:
   - Go to: Dashboard → Settings → Machine Identities
   - Click "Create Machine Identity" (if you don't have one)
   - Copy the Client ID and Client Secret
3. **Project ID**:
   - Go to: Dashboard → Projects
   - Click on your project
   - Project ID is in the URL or project settings

### Self-Hosted Infisical

1. **API URL**: `https://your-infisical-domain.com/api`
2. **Machine Identity**: Same process as cloud
3. **Project ID**: Same process as cloud

## Test Configuration

After setting up, test it:

```bash
# Test Infisical CLI
~/.local/bin/infisical-cli secrets

# Should list your secrets
```

## Security

- ✅ File permissions are set to `600` (owner read/write only)
- ✅ Never commit this file to git
- ✅ Never share credentials publicly
- ✅ File location: `~/.infisical-machine-identity`

## Next Steps

Once configured, you can:

```bash
# List all secrets
infisical-cli secrets

# Get Cloudflare Access config
infisical-cli secrets get CLOUDFLARE_ACCESS_ENABLED
infisical-cli secrets get CLOUDFLARE_ACCESS_TEAM_DOMAIN

# Export to .env.dev
infisical-cli export --format=dotenv --env=dev > .env.dev

# Set secrets
infisical-cli secrets set CLOUDFLARE_ACCESS_ENABLED=true
```
