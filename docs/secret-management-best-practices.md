# Secret Management Best Practices

This document outlines team-wide best practices for managing secrets in repositories using the claude-starter template with Infisical CLI integration.

## Philosophy

**Core Principle**: Secrets should never be committed to version control. Instead, they should be:
- Stored centrally in Infisical
- Retrieved automatically at runtime
- Environment-specific (dev/staging/prod)
- Auditable and rotatable

## Repository Setup

### 1. Initial Configuration

When creating a new repository from this template:

**Step 1**: Create Infisical project
```bash
# In Infisical dashboard:
1. Create new project (e.g., "myapp-backend")
2. Create environments: dev, staging, prod
3. Add secrets for each environment
```

**Step 2**: Create machine identity
```bash
# In Infisical project settings:
1. Go to "Machine Identities"
2. Create new identity (e.g., "development-team")
3. Grant permissions:
   - dev: read/write
   - staging: read-only
   - prod: read-only (separate identity for production)
4. Save CLIENT_ID and CLIENT_SECRET
```

**Step 3**: Document required secrets
```markdown
# Add to README.md

## Required Secrets

This project requires the following secrets configured in Infisical:

| Secret Name | Description | Example | Required For |
|------------|-------------|---------|--------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` | All environments |
| `API_KEY` | External API key | `sk_...` | All environments |
| `JWT_SECRET` | JWT signing key | Random 32 chars | All environments |
| `SMTP_*` | Email configuration | Various | Production only |

### Setup Instructions

1. Install Infisical CLI (see [Infisical Integration Guide](./docs/infisical-integration.md))
2. Request access to project: `myapp-backend` 
3. Add credentials to `~/.infisical-machine-identity`
4. Verify: `infisical-cli secrets`
```

### 2. Example Configuration Files

**Always provide `.env.example`**:

```bash
# .env.example - Commit this file
# Copy to .env.local and fill in actual values for local development without Infisical

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
DATABASE_POOL_SIZE=10

# API Keys
API_KEY=your_api_key_here
EXTERNAL_SERVICE_KEY=your_service_key

# Auth
JWT_SECRET=generate_random_32_char_string
JWT_EXPIRES_IN=7d

# Email
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=your_password
```

**Document the difference**:
```markdown
## Configuration Options

### Option 1: Infisical CLI (Recommended for teams)
```bash
infisical-cli run -- npm run dev
```

### Option 2: Local .env file (Fallback)
```bash
cp .env.example .env.local
# Edit .env.local with your local values
npm run dev
```

**Note**: Infisical is preferred for:
- ✅ Automatic secret rotation
- ✅ Audit logging
- ✅ Team secret sharing
- ✅ Environment consistency
```

## Team Workflows

### Onboarding New Developers

**1. Access Setup**
```markdown
## New Developer Checklist

- [ ] Request Infisical access from team lead
- [ ] Install Infisical CLI: `curl -LO ...`
- [ ] Create `~/.infisical-machine-identity` with provided credentials
- [ ] Test access: `infisical-cli secrets`
- [ ] Run project: `infisical-cli run -- npm run dev`
```

**2. Automated Setup Script**

Create `scripts/setup-dev.sh`:
```bash
#!/bin/bash
set -e

echo "🚀 Developer Environment Setup"
echo ""

# Check for Infisical CLI
if ! command -v infisical-cli &> /dev/null; then
    echo "❌ Infisical CLI not found"
    echo "📖 Installation guide: docs/infisical-integration.md"
    exit 1
fi

# Check credentials
if [[ ! -f "$HOME/.infisical-machine-identity" ]]; then
    echo "❌ Credentials not configured"
    echo "📖 Setup guide: docs/infisical-integration.md"
    exit 1
fi

# Test Infisical connection
echo "🔐 Testing Infisical connection..."
if ! infisical-cli secrets > /dev/null 2>&1; then
    echo "❌ Cannot connect to Infisical"
    echo "Check your credentials in ~/.infisical-machine-identity"
    exit 1
fi

echo "✅ Infisical connected successfully"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
npm install

echo ""
echo "✅ Setup complete!"
echo ""
echo "Start development with:"
echo "  npm run dev:secure"
echo ""
echo "Or with Infisical CLI directly:"
echo "  infisical-cli run -- npm run dev"
```

### Secret Rotation

**Process for rotating secrets**:

```bash
# 1. Update secret in Infisical dashboard
# (All team members automatically get new value on next run)

# 2. No code changes needed!

# 3. Notify team
echo "🔄 DATABASE_PASSWORD rotated in Infisical"
echo "Restart your development server to use new credentials"
```

**Rotation schedule**:
- **Critical secrets** (DB, API keys): Every 90 days
- **JWT secrets**: Every 180 days
- **Service tokens**: Every 30 days
- **Immediately**: If compromised or developer leaves

### Environment Management

**Development (dev)**:
- Full read/write access for all developers
- Uses test data
- Separate database from production
- OK to experiment

**Staging (staging)**:
- Read-only for developers
- Write access for CI/CD
- Mirrors production configuration
- Uses production-like data

**Production (prod)**:
- Read-only for most developers
- Separate machine identity with restricted access
- Only senior engineers + CI/CD have write access
- Requires approval for changes

## Security Policies

### 1. Git Commit Policies

**Pre-commit hook** (`.git/hooks/pre-commit`):
```bash
#!/bin/bash
# Auto-generated by claude-starter template

echo "🔍 Scanning for leaked secrets..."

# Run Infisical scan
if ! infisical-cli scan --path=. ; then
    echo ""
    echo "❌ COMMIT BLOCKED - Secrets detected!"
    echo ""
    echo "If this is a false positive, you can:"
    echo "  1. Add pattern to .infisicalignore"
    echo "  2. Run: git commit --no-verify (USE WITH CAUTION)"
    exit 1
fi

echo "✅ No secrets detected"
```

**Install for all team members**:
```bash
# scripts/install-hooks.sh
#!/bin/bash
cp hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
echo "✅ Git hooks installed"
```

### 2. Access Control Matrix

| Role | Dev Environment | Staging | Production |
|------|----------------|---------|------------|
| **Junior Developer** | Read/Write | Read | None |
| **Senior Developer** | Read/Write | Read/Write | Read |
| **Team Lead** | Read/Write | Read/Write | Read/Write |
| **CI/CD** | Read | Read | Read |

### 3. Secret Classification

**Level 1 - Critical** (Production database, payment APIs):
- Separate Infisical project
- Restricted machine identity
- Audit logs enabled
- Rotation every 30 days

**Level 2 - High** (API keys, JWT secrets):
- Standard machine identity
- Audit logs enabled
- Rotation every 90 days

**Level 3 - Medium** (SMTP, CDN):
- Standard access
- Rotation every 180 days

**Level 4 - Low** (Feature flags, config):
- Can be in .env.example
- Rotation as needed

## Documentation Standards

### In README.md

Always include:
```markdown
## Secret Management

This project uses [Infisical](https://infisical.com) for secret management.

### Quick Start

1. **Install Infisical CLI**: See [integration guide](./docs/infisical-integration.md)
2. **Get credentials**: Request access from @team-lead
3. **Configure**: Create `~/.infisical-machine-identity` with provided values
4. **Run**: `npm run dev:secure` or `infisical-cli run -- npm run dev`

### Required Secrets

See [secret management guide](./docs/secret-management-best-practices.md#required-secrets)

### Troubleshooting

- **"Credentials not found"**: Check `~/.infisical-machine-identity` exists
- **"Authentication failed"**: Verify CLIENT_ID and CLIENT_SECRET are correct
- **"Project not found"**: Request access to Infisical project
```

### In CHANGELOG.md

Document secret-related changes:
```markdown
## [1.2.0] - 2026-01-15

### Added
- New secret: `PAYMENT_API_KEY` for Stripe integration
- Environment variable: `PAYMENT_WEBHOOK_SECRET`

### Changed
- Renamed `DB_URL` to `DATABASE_URL` for consistency
- Rotated `JWT_SECRET` (all environments)

### Deprecated
- `OLD_API_KEY` - will be removed in v2.0.0
```

## CI/CD Integration

### GitHub Actions

**Recommended approach**:
```yaml
name: Test and Deploy

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
          
      - name: Export secrets to .env
        env:
          INFISICAL_TOKEN: ${{ secrets.INFISICAL_TOKEN }}
          INFISICAL_PROJECT_ID: ${{ secrets.INFISICAL_PROJECT_ID }}
        run: |
          infisical export \
            --token="$INFISICAL_TOKEN" \
            --projectId="$INFISICAL_PROJECT_ID" \
            --env=staging \
            --format=dotenv > .env
          
      - name: Run tests
        run: |
          source .env
          npm test
```

**Secret storage in GitHub**:
- Store `INFISICAL_TOKEN` as GitHub secret
- Store `INFISICAL_PROJECT_ID` as GitHub secret
- **Never** store actual application secrets in GitHub

## Incident Response

### If Secrets Are Compromised

**Immediate actions** (within 1 hour):
1. Rotate affected secrets in Infisical (all environments)
2. Check audit logs to identify scope of compromise
3. Revoke compromised machine identity
4. Create new machine identity with new credentials
5. Notify all team members

**Short-term** (within 24 hours):
1. Review all commits for additional exposed secrets
2. Scan production logs for unauthorized access
3. Update credentials for all team members
4. Document incident in security log

**Long-term** (within 1 week):
1. Conduct security review
2. Update secret scanning policies
3. Enhance pre-commit hooks if needed
4. Team training on secret management

### If Secrets Are Committed to Git

**DO NOT** just delete the commit - secrets remain in Git history!

**Correct procedure**:
```bash
# 1. Immediately rotate the secret in Infisical
# (Make the exposed secret useless)

# 2. Use BFG Repo-Cleaner or git-filter-repo
git filter-repo --path-glob '**/.env*' --invert-paths

# 3. Force push (if early enough)
git push --force origin main

# 4. If pushed to public GitHub:
# - Rotate ALL secrets immediately
# - Consider secrets permanently compromised
# - Report to security team
```

## Monitoring and Auditing

### Access Logging

**Enable Infisical audit logs**:
- Track all secret access
- Monitor for unusual patterns
- Weekly review of access logs

**Metrics to monitor**:
- Number of secret retrievals per day
- Failed authentication attempts
- Secrets accessed outside business hours
- New machine identities created

### Regular Audits

**Monthly**:
- [ ] Review all secrets in Infisical
- [ ] Remove unused secrets
- [ ] Check for secrets that should be rotated
- [ ] Verify team member access levels

**Quarterly**:
- [ ] Full security audit
- [ ] Update secret classification
- [ ] Review incident response procedures
- [ ] Team training refresher

## Troubleshooting

### Common Issues

**"Infisical CLI not found"**
```bash
# Check installation
which infisical-cli

# Add to PATH if needed
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**"Authentication failed"**
```bash
# Verify credentials file
cat ~/.infisical-machine-identity

# Test connection
infisical-cli secrets --debug
```

**"Team member can't access secrets"**
```bash
# 1. Verify machine identity has project access
# 2. Check environment permissions (dev/staging/prod)
# 3. Verify credentials file format is correct
# 4. Test with: infisical-cli secrets
```

## Additional Resources

- [Infisical Integration Guide](./infisical-integration.md) - Detailed setup and workflows
- [Official Infisical Docs](https://infisical.com/docs) - Complete documentation
- [OWASP Secret Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

---

**Last Updated**: 2026-01-14  
**Review Frequency**: Quarterly  
**Owner**: Development Team Lead
