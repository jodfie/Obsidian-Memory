# Bitwarden Secrets Manager Setup Guide

This guide explains how to configure Bitwarden Secrets Manager credentials so the assistant can use them to manage secrets.

## Step 1: Get Your Bitwarden Secrets Manager Credentials

You need the following information from your Bitwarden Secrets Manager instance:

1. **BWS_ACCESS_TOKEN** - Machine Account Access Token (Machine Identifier Key)
   - Found in: Bitwarden Secrets Manager → Machine Accounts → Your Account → Access Tokens
   - Create a new access token if you don't have one
   - **Copy immediately - it's only shown once!**

2. **BWS_SERVER_URL** - Your Bitwarden server URL (optional)
   - Default: `https://vault.bitwarden.com` (Bitwarden Cloud)
   - For self-hosted: `https://your-bitwarden-instance.com`

3. **BWS_PROJECT_ID** - Project ID (optional)
   - Only needed if using projects to organize secrets
   - Found in: Bitwarden Secrets Manager → Projects → Your Project

4. **BWS_ENVIRONMENT** - Environment name (optional)
   - Used for organization: `dev`, `staging`, `prod`
   - Not required but recommended for multi-environment setups

## Step 2: Create Machine Account and Access Token

### In Bitwarden Secrets Manager:

1. **Create Machine Account**:
   - Log into Bitwarden Secrets Manager web app
   - Use the **New** dropdown → Select **Machine account**
   - Enter a name (e.g., "VPS-Production" or "Obsidian-Memory-Server")
   - Save

2. **Configure Permissions**:
   - Open the machine account
   - Navigate to **Projects** tab
   - Select projects the machine account needs to access
   - Assign permission: **Can read** or **Can read, write**

3. **Generate Access Token**:
   - In machine account view, go to **Access tokens** tab
   - Click **New access token**
   - Provide a name (e.g., "VPS-Access-Token")
   - **Copy the token immediately** - it won't be shown again!

## Step 3: Create Credentials File

### Option 1: Use Setup Script (Recommended)

```bash
./scripts/setup-bitwarden.sh
```

The script will:
- Prompt for your credentials
- Create `~/.bitwarden-machine-identity` file
- Set proper permissions (600)
- Test the configuration

### Option 2: Manual Setup

Create the credentials file manually:

```bash
cat > ~/.bitwarden-machine-identity <<'EOF'
BWS_ACCESS_TOKEN="your-access-token-here"
BWS_SERVER_URL="https://vault.bitwarden.com"
BWS_PROJECT_ID="your-project-id"  # Optional
BWS_ENVIRONMENT="prod"              # Optional
EOF

chmod 600 ~/.bitwarden-machine-identity
```

**Important**: Replace the placeholder values with your actual credentials!

## Step 4: Install Bitwarden Secrets Manager CLI

### Linux (VPS)

```bash
# Download latest release
curl -L https://github.com/bitwarden/sdk/releases/latest/download/bws-linux -o /usr/local/bin/bws

# Make executable
chmod +x /usr/local/bin/bws

# Verify installation
bws --version
```

### Alternative: Manual Download

1. Visit: https://github.com/bitwarden/sdk/releases
2. Download `bws-linux` (or appropriate binary for your system)
3. Move to `/usr/local/bin/` or add to PATH
4. Make executable: `chmod +x /usr/local/bin/bws`

## Step 5: Test Configuration

```bash
# Source credentials
source ~/.bitwarden-machine-identity

# Test connection
bws secret list

# Get a specific secret (if you know the ID)
bws secret get <secret-id>
```

If it works, you should see a list of secrets or the secret value.

## Step 6: Verify PATH (Optional)

If `bws` command is not found, add to PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Where to Find Credentials

### Bitwarden Cloud (vault.bitwarden.com)

1. **Server URL**: `https://vault.bitwarden.com` (default)
2. **Machine Account**: 
   - Log into Bitwarden Secrets Manager
   - Navigate to Machine Accounts
   - Create new or use existing
3. **Access Token**: 
   - Machine Account → Access Tokens tab
   - Create new token
   - Copy immediately (shown only once)

### Self-Hosted Bitwarden

1. **Server URL**: `https://your-bitwarden-instance.com`
2. **Machine Account**: Same as cloud
3. **Access Token**: Same as cloud

## Using with This Project

Once configured, you can:

```bash
# Source credentials
source ~/.bitwarden-machine-identity

# List secrets
bws secret list

# Get specific secret
bws secret get <secret-id>

# Run application with secrets injected as environment variables
bws run -- npm run dev
bws run -- python app.py
bws run -- uvicorn app:app --reload

# Export secrets to .env file (for local development only)
bws secret list --format json | jq -r '.[] | "\(.key)=\(.value)"' > .env.local
```

## Environment Variable Usage

You can also set the access token directly in your environment:

```bash
# In ~/.bashrc or ~/.zshrc
export BWS_ACCESS_TOKEN="your-access-token-here"
export BWS_SERVER_URL="https://vault.bitwarden.com"

# Or source the credentials file
source ~/.bitwarden-machine-identity
```

## Security Notes

- ✅ File permissions: `600` (owner read/write only)
- ✅ Never commit this file to git
- ✅ Never share access tokens
- ✅ Rotate tokens if compromised
- ✅ Use different machine accounts for dev/staging/prod
- ✅ Access tokens are shown only once - store securely

## Integration with Application

### Python (FastAPI)

```python
import os
import subprocess
from pathlib import Path

def load_bitwarden_secrets():
    """Load secrets from Bitwarden Secrets Manager."""
    creds_file = Path.home() / ".bitwarden-machine-identity"
    if creds_file.exists():
        # Source credentials
        with open(creds_file) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"')
    
    # Use bws CLI to get secrets
    result = subprocess.run(
        ['bws', 'secret', 'list', '--format', 'json'],
        capture_output=True,
        text=True
    )
    # Parse and set environment variables
```

### Shell Scripts

```bash
#!/bin/bash
# Source Bitwarden credentials
source ~/.bitwarden-machine-identity

# Get a secret value
SECRET_VALUE=$(bws secret get <secret-id> --format json | jq -r '.value')

# Use in your script
export DATABASE_URL="$SECRET_VALUE"
```

## Troubleshooting

### "bws: command not found"
- Check installation: `which bws`
- Verify PATH includes `/usr/local/bin`
- Reinstall if needed

### "Authentication failed"
- Verify access token is correct
- Check token hasn't expired or been revoked
- Verify machine account has proper permissions

### "Project not found"
- Verify PROJECT_ID is correct (if using projects)
- Check machine account has access to the project

### "Server connection failed"
- Verify BWS_SERVER_URL is correct
- Check network connectivity
- For self-hosted, verify SSL certificate

## Comparison with Infisical

| Feature | Bitwarden Secrets Manager | Infisical |
|---------|---------------------------|-----------|
| Authentication | Access Token | Client ID + Secret |
| CLI Tool | `bws` | `infisical-cli` |
| Credentials File | `~/.bitwarden-machine-identity` | `~/.infisical-machine-identity` |
| Secret Injection | `bws run -- <command>` | `infisical-cli run -- <command>` |
| Projects | Optional | Required |

## Next Steps

After configuring credentials:

1. Test: `source ~/.bitwarden-machine-identity && bws secret list`
2. Set up secrets in Bitwarden Secrets Manager dashboard
3. Integrate with your application:
   ```bash
   # Run with secrets injected
   source ~/.bitwarden-machine-identity
   bws run -- python -m app.main
   ```

## Additional Resources

- [Bitwarden Secrets Manager CLI Docs](https://bitwarden.com/help/secrets-manager-cli/)
- [Machine Accounts Guide](https://bitwarden.com/help/machine-accounts/)
- [Secrets Manager Quick Start](https://bitwarden.com/help/secrets-manager-quick-start/)
- [SDK GitHub Repository](https://github.com/bitwarden/sdk)

---

**Last Updated**: 2026-01-14  
**Review Frequency**: Quarterly  
**Owner**: Development Team Lead
