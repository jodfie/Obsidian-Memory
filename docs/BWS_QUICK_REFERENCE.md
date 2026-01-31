# Bitwarden Secrets Manager - Quick Reference

## Automatic Setup

Your `~/.bashrc` is now configured to automatically:
- ✅ Load Bitwarden credentials on shell startup
- ✅ Add `bws` CLI to PATH
- ✅ Provide helper functions and aliases

**Just open a new terminal** and everything will be ready!

## Helper Functions (Available in Your Shell)

### List Secrets
```bash
# List all secrets
bws-list

# List secrets in a specific project
bws-list <project-id>
```

### Get Secret Value
```bash
# Get secret by ID
bws-get <secret-id>

# Get secret by key name
bws-get DATABASE_URL
```

### Add New Secret
```bash
# Add a secret (will prompt for project if needed)
bws-add <key> <value> [project-id]

# Examples:
bws-add DATABASE_URL "postgresql://user:pass@localhost/db"
bws-add API_KEY "sk_1234567890" <project-id>
```

### List Projects
```bash
bws-projects
```

### Export Secrets
```bash
# Export as .env format (to stdout)
bws-export dotenv

# Export to file
bws-export dotenv .env.local

# Export as JSON
bws-export json
```

### Run Command with Secrets
```bash
# Run any command with secrets injected as environment variables
bws-run python app.py
bws-run npm start
bws-run uvicorn app:app --reload
```

## Interactive Scripts

### Add Secret (Interactive)
```bash
./scripts/bws-add-secret.sh
```
Prompts for:
- Secret key
- Secret value (hidden input)
- Project ID (optional)
- Note/description (optional)

### List Secrets (Formatted)
```bash
# List all secrets
./scripts/bws-list-secrets.sh

# List secrets in project
./scripts/bws-list-secrets.sh <project-id>

# Output as JSON
./scripts/bws-list-secrets.sh "" json
```

## Direct bws CLI Commands

Since credentials are auto-loaded, you can use `bws` directly:

```bash
# List projects
bws project list

# List secrets
bws secret list
bws secret list --project-id <project-id>

# Get secret
bws secret get <secret-id>

# Create secret
bws secret create --key "KEY" --value "VALUE" --project-id <project-id>

# Update secret
bws secret update <secret-id> --value "NEW_VALUE"

# Delete secret
bws secret delete <secret-id>

# Run command with secrets
bws run -- <command>
```

## Examples

### Example 1: Add Database Credentials
```bash
# Interactive way
./scripts/bws-add-secret.sh
# Enter: DATABASE_URL
# Enter: postgresql://user:pass@localhost/dbname
# Enter: <project-id>

# Or using function
bws-add DATABASE_URL "postgresql://user:pass@localhost/dbname" <project-id>
```

### Example 2: Get Secret Value
```bash
# By key name
bws-get DATABASE_URL

# By ID
bws-get abc123def456
```

### Example 3: Export All Secrets to .env
```bash
bws-export dotenv > .env.local
```

### Example 4: Run Application with Secrets
```bash
# Python
bws-run python -m app.main

# Node.js
bws-run npm start

# FastAPI
bws-run uvicorn app:app --reload
```

### Example 5: List All Secrets in Table Format
```bash
bws-list | jq -r '.[] | "\(.key) = \(.value)"'
```

## Environment Variables

After opening a new terminal, these are automatically set:
- `BWS_ACCESS_TOKEN` - Your access token
- `BWS_SERVER_URL` - Server URL (https://vault.bitwarden.com)
- `BWS_ORGANIZATION_ID` - Your organization ID

## Troubleshooting

### Functions Not Available
If functions aren't available, open a new terminal or run:
```bash
source ~/.bashrc
```

### "bws: command not found"
The PATH should be set automatically. If not:
```bash
export PATH="$PATH:$HOME/.local/bin"
```

### "Authentication failed"
Check your credentials:
```bash
echo $BWS_ACCESS_TOKEN
source ~/.bitwarden-machine-identity
```

## Quick Commands Cheat Sheet

```bash
# Setup (one-time, already done)
source ~/.bitwarden-machine-identity

# List everything
bws-projects          # List projects
bws-list              # List secrets

# Get secret
bws-get KEY_NAME      # Get by key
bws-get secret-id     # Get by ID

# Add secret
bws-add KEY VALUE [project-id]

# Export
bws-export dotenv > .env

# Run with secrets
bws-run <command>
```

## Files Reference

- `~/.bitwarden-machine-identity` - Credentials (auto-loaded)
- `~/.bashrc` - Shell configuration (auto-loads credentials)
- `scripts/bws-add-secret.sh` - Interactive secret creation
- `scripts/bws-list-secrets.sh` - Formatted secret listing
- `scripts/bitwarden-helper.sh` - General helper script

---

**Note**: All functions are available in new terminal sessions automatically!
