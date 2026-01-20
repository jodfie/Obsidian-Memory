# Infisical CLI Setup Guide

This guide explains how to configure Infisical CLI credentials so the assistant can use them to manage secrets.

## Step 1: Get Your Infisical Credentials

You need the following information from your Infisical instance:

1. **INFISICAL_API_URL** - Your Infisical instance API URL
   - Example: `https://infisical.yourdomain.com/api`
   - Or: `https://app.infisical.com/api` (for cloud)

2. **INFISICAL_CLIENT_ID** - Machine Identity Client ID
   - Found in: Infisical Dashboard → Settings → Machine Identities
   - Create a new machine identity if you don't have one

3. **INFISICAL_CLIENT_SECRET** - Machine Identity Client Secret
   - Generated when creating machine identity
   - **Keep this secret!**

4. **INFISICAL_PROJECT_ID** - Project ID for this repository
   - Found in: Infisical Dashboard → Projects → Your Project
   - Usually a UUID or short identifier

5. **INFISICAL_ENVIRONMENT** - Environment name
   - Options: `dev`, `staging`, `prod`
   - Default: `dev`

6. **INFISICAL_SECRET_PATH** - Path within project
   - Default: `/` (root)
   - Can be: `/backend`, `/frontend`, etc.

## Step 2: Create Credentials File

Create the credentials file with your values:

```bash
cat > ~/.infisical-machine-identity <<'EOF'
INFISICAL_API_URL="https://your-infisical-instance.com/api"
INFISICAL_CLIENT_ID="your-machine-identity-client-id"
INFISICAL_CLIENT_SECRET="your-machine-identity-client-secret"
INFISICAL_PROJECT_ID="your-project-id"
INFISICAL_ENVIRONMENT="dev"
INFISICAL_SECRET_PATH="/"
EOF
```

**Important**: Replace the placeholder values with your actual credentials!

## Step 3: Set Proper Permissions

```bash
chmod 600 ~/.infisical-machine-identity
```

This ensures only you can read the file.

## Step 4: Test Configuration

```bash
# Test Infisical CLI
~/.local/bin/infisical-cli secrets

# Or if ~/.local/bin is in PATH:
infisical-cli secrets
```

If it works, you should see a list of secrets.

## Step 5: Verify PATH (Optional)

If `infisical-cli` command is not found, add to PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Where to Find Credentials

### Infisical Cloud (app.infisical.com)

1. **API URL**: `https://app.infisical.com/api`
2. **Machine Identity**: 
   - Dashboard → Settings → Machine Identities
   - Click "Create Machine Identity"
   - Copy Client ID and Client Secret
3. **Project ID**: 
   - Dashboard → Projects
   - Click on your project
   - Project ID is shown in URL or project settings

### Self-Hosted Infisical

1. **API URL**: `https://your-infisical-domain.com/api`
2. **Machine Identity**: Same as cloud
3. **Project ID**: Same as cloud

## Example Credentials File

```bash
# ~/.infisical-machine-identity
INFISICAL_API_URL="https://app.infisical.com/api"
INFISICAL_CLIENT_ID="64a1b2c3d4e5f6g7h8i9j0k1"
INFISICAL_CLIENT_SECRET="sk_live_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"
INFISICAL_PROJECT_ID="64a1b2c3d4e5f6g7h8i9j0k1"
INFISICAL_ENVIRONMENT="dev"
INFISICAL_SECRET_PATH="/"
```

## Security Notes

- ✅ File permissions: `600` (owner read/write only)
- ✅ Never commit this file to git
- ✅ Never share credentials
- ✅ Rotate credentials if compromised
- ✅ Use different machine identities for dev/staging/prod

## Using with This Project

Once configured, you can:

```bash
# List secrets
infisical-cli secrets

# Get specific secret
infisical-cli secrets get CLOUDFLARE_ACCESS_ENABLED

# Set secret
infisical-cli secrets set CLOUDFLARE_ACCESS_ENABLED=true

# Export all secrets to .env.dev
infisical-cli export --format=dotenv --env=dev > .env.dev

# Run commands with secrets injected
infisical-cli run -- docker compose up -d
```

## Troubleshooting

### "Credentials file not found"
- Check file exists: `ls -la ~/.infisical-machine-identity`
- Check permissions: `chmod 600 ~/.infisical-machine-identity`

### "Authentication failed"
- Verify credentials are correct
- Check machine identity is active
- Verify API URL is correct

### "Project not found"
- Verify PROJECT_ID is correct
- Check machine identity has access to project
- Verify environment name is correct

## Next Steps

After configuring credentials:

1. Test: `infisical-cli secrets`
2. Set Cloudflare Access secrets:
   ```bash
   infisical-cli secrets set CLOUDFLARE_ACCESS_ENABLED=true
   infisical-cli secrets set CLOUDFLARE_ACCESS_TEAM_DOMAIN=redleif.cloudflareaccess.com
   ```
3. Export to `.env.dev`:
   ```bash
   infisical-cli export --format=dotenv --env=dev > .env.dev
   ```
