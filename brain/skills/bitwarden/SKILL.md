---
name: bitwarden
description: Comprehensive Bitwarden integration supporting both personal CLI (bw) and Secrets Manager CLI (bws). Use for password management, secure storage of API keys, secrets injection into commands, team secrets management, and automated credential retrieval. Supports login, vault access, item creation/update, secrets management, and environment variable injection.
---

# Bitwarden Skill

Comprehensive Bitwarden integration supporting both personal vault management (`bw` CLI) and enterprise secrets management (`bws` CLI).

## Quick Start

### Personal Vault (bw)
```bash
# Login and unlock
bw login
bw unlock  # Sets session key

# Search and retrieve password
bw get password "github.com"
bw get item "my-api-key" | jq -r '.notes'

# Create new item
echo '{"type": 1, "name": "New Service", "login": {"username": "user", "password": "pass"}}' | bw encode | bw create item
```

### Secrets Manager (bws)
```bash
# Set access token
export BWS_ACCESS_TOKEN="your-token"

# Run command with secrets injected
bws run -- ./deploy.sh

# Get specific secret
bws secret get SECRET_ID
```

---

## Personal CLI (bw)

### Authentication
```bash
bw login                           # Initial login
bw unlock                          # Unlock vault (provides session key)
bw lock                           # Lock vault
bw logout                         # Sign out
bw status                         # Check login/unlock status
```

### Retrieving Items
```bash
# Get password by name
bw get password "GitHub"
bw get password "github.com"

# Get username
bw get username "github.com"

# Get full item details
bw get item "GitHub" | jq '.'

# Get notes field
bw get notes "API Keys"

# Search items
bw list items --search "aws"
bw list items --search "database" | jq '.[].name'
```

### Creating Items

See [references/create-items.md](references/create-items.md) for detailed templates and examples.

### Organization
```bash
# List folders
bw list folders

# Create folder
echo '{"name": "Work Accounts"}' | bw encode | bw create folder

# List organizations
bw list organizations
```

### Sync and Status
```bash
bw sync                           # Sync with server
bw status                         # Login/unlock status
bw --version                      # Version info
```

---

## Secrets Manager CLI (bws)

### Setup
```bash
# Install (if needed)
npm install -g @bitwarden/sdk

# Set access token
export BWS_ACCESS_TOKEN="your-token-here"

# Test connection
bws project list
```

### Secret Injection
```bash
# Run command with secrets as environment variables
bws run -- ./script.sh

# Run with specific project
bws run --project-id PROJECT_ID -- node app.js

# Echo a secret by name
bws run -- 'echo "$SECRET_NAME"'

# Docker compose with secrets
bws run -- 'docker compose up -d'
```

### Direct Secret Access
```bash
# List projects
bws project list

# List secrets in project
bws secret list --project-id PROJECT_ID

# Get specific secret
bws secret get SECRET_ID

# Create secret
bws secret create SECRET_NAME "secret-value" --project-id PROJECT_ID

# Update secret
bws secret edit SECRET_ID --value "new-value"
```

### Project Management
```bash
# List projects
bws project list

# Create project
bws project create "My Project"

# Get project details
bws project get PROJECT_ID
```

---

## Common Patterns

### Automated Deployment
```bash
# Deploy with secrets injection
bws run -- './deploy.sh'

# Docker with secrets
bws run -- 'docker run -e DATABASE_URL -e API_KEY my-app'
```

### Development Workflow
```bash
# Start dev server with secrets
bws run -- 'npm start'

# Run tests with test credentials
bws run --project-id TEST_PROJECT -- 'npm test'
```

### Backup Critical Secrets
```bash
# Export secrets (careful with security)
bws secret list --project-id PROJECT_ID --format json > backup.json

# Import from personal vault to secrets manager (manual process)
# 1. bw get item "service" | jq -r '.notes'
# 2. bws secret create "SERVICE_API_KEY" "value" --project-id PROJECT_ID
```

---

## Authentication Helpers

### Personal Vault Session Management

See [scripts/bw-session.sh](scripts/bw-session.sh) for session key management.

### Secrets Manager Token Management

For security, store BWS tokens in:
1. macOS Keychain: `security add-generic-password -s BWS_TOKEN -a $(whoami) -w`
2. Environment file: `echo 'export BWS_ACCESS_TOKEN="token"' >> ~/.bw_secrets`
3. Vault itself: Store in personal Bitwarden as secure note

---

## When to Use Which Tool

**Use `bw` (Personal CLI) for:**
- Personal password management
- Individual developer credentials
- SSH keys, personal API tokens
- Small team shared passwords
- Development/staging credentials

**Use `bws` (Secrets Manager) for:**
- Production application secrets
- CI/CD pipeline credentials
- Team-managed infrastructure secrets
- Automated deployments
- Environment-specific configurations

**Migration path:** Start with `bw` for personal use, migrate to `bws` when you need team management and automated injection.

---

## Security Notes

- **Never commit session keys or access tokens**
- **Use `bw lock` when stepping away**
- **Rotate BWS tokens regularly**
- **Use project-specific tokens when possible**
- **Audit secret access via Bitwarden web vault**

For detailed examples and templates, see the reference files.