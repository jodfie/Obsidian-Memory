# Infisical CLI Integration Guide

This guide demonstrates how to integrate Infisical CLI into your development workflow for automated secret management.

## Overview

Infisical CLI provides secure, automated access to secrets without manual copy-paste or committing sensitive data. The CLI is installed globally on your development machine, not per-repository.

## Prerequisites

### 1. Install Infisical CLI

The official Infisical CLI and wrapper must be installed on your host system:

```bash
# Download and install official CLI
cd /tmp
curl -LO "https://github.com/Infisical/cli/releases/download/v0.43.46/cli_0.43.46_linux_amd64.tar.gz"
tar -xzf cli_0.43.46_linux_amd64.tar.gz
mv infisical ~/.local/bin/
chmod +x ~/.local/bin/infisical
```

### 2. Set Up Wrapper Script

Create `~/.local/bin/infisical-cli` with auto-configuration:

```bash
#!/bin/bash
# Auto-configured Infisical CLI wrapper
# Sources credentials from ~/.infisical-machine-identity

CREDS_FILE="$HOME/.infisical-machine-identity"

if [[ ! -f "$CREDS_FILE" ]]; then
    echo "Error: Credentials file not found at $CREDS_FILE"
    exit 1
fi

# Source credentials
source "$CREDS_FILE"

# Get fresh token
export INFISICAL_TOKEN=$(infisical login --method=universal-auth \
    --client-id="$INFISICAL_CLIENT_ID" \
    --client-secret="$INFISICAL_CLIENT_SECRET" \
    --domain="$INFISICAL_API_URL" \
    --silent)

# Run command with auto-injected config
exec infisical "$@" \
    --domain="$INFISICAL_API_URL" \
    --projectId="$INFISICAL_PROJECT_ID" \
    --env="$INFISICAL_ENVIRONMENT" \
    --path="$INFISICAL_SECRET_PATH"
```

```bash
chmod +x ~/.local/bin/infisical-cli
```

### 3. Configure Credentials

Create `~/.infisical-machine-identity`:

```bash
# Infisical Machine Identity Credentials
INFISICAL_API_URL="https://your-infisical-instance.com/api"
INFISICAL_CLIENT_ID="your-client-id"
INFISICAL_CLIENT_SECRET="your-client-secret"
INFISICAL_PROJECT_ID="your-project-id"
INFISICAL_ENVIRONMENT="dev"
INFISICAL_SECRET_PATH="/"
```

**Security Note**: This file should have restricted permissions:
```bash
chmod 600 ~/.infisical-machine-identity
```

## Development Workflows

### Node.js / TypeScript Projects

**Development server with secrets**:
```bash
# Instead of manually creating .env files
infisical-cli run -- npm run dev

# Run tests with secrets
infisical-cli run -- npm test

# Build with secrets (if needed during build)
infisical-cli run -- npm run build

# Run production build locally
infisical-cli run -- npm start
```

**Package scripts integration** (package.json):
```json
{
  "scripts": {
    "dev": "next dev",
    "dev:secure": "infisical-cli run -- npm run dev",
    "test": "jest",
    "test:secure": "infisical-cli run -- npm test"
  }
}
```

### Python Projects

**Django development**:
```bash
# Run development server with secrets
infisical-cli run -- python manage.py runserver

# Run migrations with DB credentials
infisical-cli run -- python manage.py migrate

# Run tests
infisical-cli run -- python manage.py test

# Shell with secrets loaded
infisical-cli run -- python manage.py shell
```

**FastAPI/uvicorn**:
```bash
# Development with auto-reload
infisical-cli run -- uvicorn app:app --reload

# Production mode
infisical-cli run -- uvicorn app:app --host 0.0.0.0 --port 8000
```

**Generic Python scripts**:
```bash
# Run any Python script with secrets
infisical-cli run -- python script.py

# With virtual environment
infisical-cli run -- .venv/bin/python app.py
```

### Go Projects

**Development server**:
```bash
# Run with auto-reloading (using air or similar)
infisical-cli run -- air

# Direct go run
infisical-cli run -- go run main.go

# Run tests with secrets
infisical-cli run -- go test ./...

# Build binary with secrets available during build
infisical-cli run -- go build -o app
```

### Docker Development

**Docker Compose with secrets**:
```bash
# Export secrets to .env for docker-compose
infisical-cli export --format=dotenv > .env.local

# Then use in docker-compose.yml
docker-compose --env-file .env.local up
```

**Build-time secrets**:
```dockerfile
# Dockerfile with build args
ARG API_KEY
ARG DATABASE_URL

# Use secrets during build
RUN ./configure.sh
```

```bash
# Build with secrets injected
infisical-cli run -- docker build \
  --build-arg API_KEY=$API_KEY \
  --build-arg DATABASE_URL=$DATABASE_URL \
  -t myapp .
```

### CI/CD Integration

**GitHub Actions**:
```yaml
name: Build and Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Infisical CLI
        run: |
          curl -LO "https://github.com/Infisical/cli/releases/download/v0.43.46/cli_0.43.46_linux_amd64.tar.gz"
          tar -xzf cli_0.43.46_linux_amd64.tar.gz
          sudo mv infisical /usr/local/bin/
          
      - name: Export secrets
        env:
          INFISICAL_TOKEN: ${{ secrets.INFISICAL_TOKEN }}
        run: |
          infisical export --format=dotenv > .env
          
      - name: Run tests
        run: |
          source .env
          npm test
```

**GitLab CI**:
```yaml
test:
  image: node:18
  before_script:
    - curl -LO "https://github.com/Infisical/cli/releases/download/v0.43.46/cli_0.43.46_linux_amd64.tar.gz"
    - tar -xzf cli_0.43.46_linux_amd64.tar.gz
    - mv infisical /usr/local/bin/
    - infisical export --format=dotenv > .env
  script:
    - source .env
    - npm install
    - npm test
```

## Secret Management Best Practices

### 1. Never Commit Secrets

Always use `.gitignore` patterns:

```gitignore
# Secret files
.env
.env.local
.env.*.local

# Keep example files
!.env.example
!.env.template

# Credential files
*credentials*.json
*secrets*.json
```

### 2. Provide Example Configuration

Create `.env.example` with placeholder values:

```bash
# .env.example
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
API_KEY=your_api_key_here
JWT_SECRET=your_jwt_secret_here
```

Commit this file to version control so developers know what secrets are required.

### 3. Document Required Secrets

In your `README.md`, list all required secrets:

```markdown
## Required Secrets

This project requires the following secrets in Infisical:

- `DATABASE_URL` - PostgreSQL connection string
- `API_KEY` - External API authentication key  
- `JWT_SECRET` - JWT signing secret (32+ random chars)
- `SMTP_HOST` - Email server hostname
- `SMTP_USER` - Email server username
- `SMTP_PASSWORD` - Email server password
```

### 4. Use Security Scanning

Run Infisical scan before commits:

```bash
# Scan entire project
infisical-cli scan

# Scan specific directory
infisical-cli scan --path=./src

# Scan with verbose output
infisical-cli scan --verbose
```

**Pre-commit hook** (.git/hooks/pre-commit):
```bash
#!/bin/bash
echo "Scanning for leaked secrets..."
if ! infisical-cli scan; then
    echo "❌ Secret scan failed! Commit blocked."
    exit 1
fi
echo "✅ No secrets detected"
```

### 5. Environment-Specific Secrets

Configure different Infisical environments:

```bash
# Development (default)
export INFISICAL_ENVIRONMENT="dev"
infisical-cli run -- npm run dev

# Staging
export INFISICAL_ENVIRONMENT="staging"
infisical-cli run -- npm run dev

# Production (use with caution!)
export INFISICAL_ENVIRONMENT="prod"
infisical-cli run -- npm start
```

**Per-environment wrapper scripts**:

```bash
# dev.sh
#!/bin/bash
INFISICAL_ENVIRONMENT=dev infisical-cli run -- npm run dev

# staging.sh
#!/bin/bash
INFISICAL_ENVIRONMENT=staging infisical-cli run -- npm run dev
```

## Common Patterns

### Pattern 1: Local Development Only

For projects where secrets are only needed locally (not in CI):

```bash
# Developer runs app locally with secrets
infisical-cli run -- npm run dev

# CI runs without secrets (uses mocked services)
npm run test:ci
```

### Pattern 2: Local + CI

For projects requiring secrets in both local and CI:

**Local** (using wrapper):
```bash
infisical-cli run -- npm test
```

**CI** (using token):
```yaml
- name: Run tests with secrets
  env:
    INFISICAL_TOKEN: ${{ secrets.INFISICAL_TOKEN }}
  run: |
    infisical export --format=dotenv > .env
    source .env
    npm test
```

### Pattern 3: Hybrid (Some Local, Some Infisical)

For projects with a mix of local and centralized secrets:

```bash
# .env.local (developer-specific, gitignored)
DEBUG=true
LOG_LEVEL=debug

# Infisical (shared team secrets)
DATABASE_URL=<from-infisical>
API_KEY=<from-infisical>
```

Run with both:
```bash
# Load local .env.local, then inject Infisical secrets
export $(cat .env.local | xargs)
infisical-cli run -- npm run dev
```

## Quick Reference

### Essential Commands

```bash
# List all secrets
infisical-cli secrets

# Get specific secret
infisical-cli secrets get SECRET_NAME

# Run app with secrets
infisical-cli run -- <your-command>

# Export to .env
infisical-cli export --format=dotenv > .env

# Security scan
infisical-cli scan

# Get help
infisical-cli --help
```

### Quick Secret Retrieval (Scripts)

For shell scripts needing a single secret:

```bash
#!/bin/bash
# Use infisical-helper for single-secret retrieval
DB_PASSWORD=$(infisical-helper get DATABASE_PASSWORD)

# Use in script
psql -h localhost -U user -d mydb
```

## Troubleshooting

### "Credentials file not found"

**Problem**: `~/.infisical-machine-identity` doesn't exist.

**Solution**: Create the file with your Infisical credentials:
```bash
cat > ~/.infisical-machine-identity <<EOF
INFISICAL_API_URL="https://your-instance.com/api"
INFISICAL_CLIENT_ID="your-id"
INFISICAL_CLIENT_SECRET="your-secret"
INFISICAL_PROJECT_ID="your-project-id"
INFISICAL_ENVIRONMENT="dev"
INFISICAL_SECRET_PATH="/"
EOF
chmod 600 ~/.infisical-machine-identity
```

### "Command not found: infisical-cli"

**Problem**: CLI not in PATH.

**Solution**: Ensure `~/.local/bin` is in your PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### "Authentication failed"

**Problem**: Invalid credentials or expired token.

**Solution**: Verify credentials in `~/.infisical-machine-identity` are correct and active.

### "Project not found"

**Problem**: Wrong `INFISICAL_PROJECT_ID` or insufficient permissions.

**Solution**: 
1. Verify project ID in Infisical dashboard
2. Check machine identity has access to the project

## Additional Resources

- **Official Docs**: https://infisical.com/docs/cli/overview
- **TechKB** (if available on host): 
  - `TechKB/40-services/infisical/Infisical-Setup.md`
  - `TechKB/80-reference/quick-ref/Infisical-Commands.md`
- **GitHub**: https://github.com/Infisical/cli

---

**Last Updated**: 2026-01-14  
**Compatible With**: Infisical CLI v0.43.46+
