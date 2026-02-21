# Deployment Infrastructure Setup Prompt

Use this prompt with a local agent to set up Obsidian-Memory deployment infrastructure.

---

## Dev Mode: Obsidian-Memory Deployment Infrastructure

### Permissions Granted
- Create/modify Docker configuration files
- Create git branches (dev, main)
- Write deployment documentation
- Execute docker compose commands
- Configure Traefik labels
- Create GitHub Actions workflows
- Modify .env files

### SAFETY BOUNDARIES (Hard Rules)
- DO NOT delete existing working containers
- DO NOT modify production environment until dev is fully tested
- DO NOT commit secrets to git (use .env files, add to .gitignore)
- ASK before any destructive operations

Proceed autonomously within these bounds. Execute commands, don't just show them.

---

## Phase 1: Discovery
Before making changes, assess current state:
```bash
# Check existing project structure
ls -la
cat package.json 2>/dev/null || echo "No package.json"
cat Dockerfile 2>/dev/null || echo "No Dockerfile"
ls docker* 2>/dev/null || echo "No docker files"
git branch -a
git remote -v
```

Report findings before proceeding.

---

## Phase 2: Git Branch Strategy

Create branching structure:
- `dev` branch = development/staging environment
- `main` branch = production releases
- Feature branches → merge to dev → merge to main

```bash
# Ensure dev branch exists
git checkout dev || git checkout -b dev
git push -u origin dev || echo "dev branch already exists"

# Ensure main branch exists
git checkout main || git checkout -b main
git push -u origin main || echo "main branch already exists"
```

---

## Phase 3: Docker Configuration

### 3.1 Create Multi-Stage Dockerfile

Create `Dockerfile` at project root with dev and prod targets:
- Dev target: hot reload, debug logging, development dependencies
- Prod target: optimized build, minimal image, no dev deps
- Use port 8765 for the service
- Include docker-entrypoint.sh

### 3.2 Create docker-compose.yml (Base)

Base configuration shared between environments:
- Service definition named `memory`
- Volume mounts for vault data (`/data` and `/vaults`)
- Network configuration (use `proxy` network for Traefik - external)
- Environment variables from .env files

### 3.3 Create docker-compose.dev.yml

Development overrides:
- Container name: `memory-dev`
- Build target: `dev`
- Port mapping: `8766:8765` (different port for dev)
- Hot reload volume mount: `./backend:/app/backend:cached`
- Traefik labels for `memory-dev.example.com`
- Debug logging enabled

### 3.4 Create docker-compose.prod.yml

Production overrides:
- Container name: `memory`
- Build target: `prod`
- Resource limits: 512M memory, 0.5 CPU
- Traefik labels for `memory.example.com`
- Log rotation configured
- Health check with longer start period

---

## Phase 4: Environment Configuration

### 4.1 Create .env.example
Template with all required variables (no actual secrets):
- BASIC_MEMORY_HOME
- LOG_LEVEL
- VAULT_PATH
- GIT_AUTO_COMMIT
- REQUIRE_AUTH
- API_TOKEN (placeholder)
- ANTHROPIC_API_KEY (placeholder)
- etc.

### 4.2 Create .env.dev.example and .env.prod.example
Separate templates for dev and prod environments.

### 4.3 Update .gitignore
Ensure .env files are ignored but .env.example files are tracked:
```
.env
.env.dev
.env.prod
!.env.example
!.env.dev.example
!.env.prod.example
```

---

## Phase 5: Deployment Scripts

### 5.1 Create Makefile
Commands needed:
- `make setup` - Copy environment templates
- `make dev` - Start development environment
- `make prod` - Start production environment
- `make build` - Build Docker images
- `make logs-dev` / `make logs-prod` - View logs
- `make stop-dev` / `make stop-prod` - Stop services
- `make restart-dev` / `make restart-prod` - Restart services
- `make health` / `make health-dev` - Health checks
- `make clean` - Cleanup

### 5.2 Create docker-entrypoint.sh
Environment-specific startup logic:
- Create data directories
- Set permissions
- Export environment variables
- Optional health check wait
- Execute the command

---

## Phase 6: CI/CD with GitHub Actions

### 6.1 Create .github/workflows/ci.yml
- Test job: Run pytest, type checking, linting
- Build job: Build Docker image and test
- Deploy-dev job: Deploy to dev on push to dev branch
- Deploy-prod job: Deploy to prod on push to main (requires manual approval)

### 6.2 Create .github/workflows/docker-publish.yml
- Build and push to GHCR on tag push
- Tag images with version, branch, SHA
- Support both dev and prod targets

---

## Phase 7: Health Check Endpoint

Enhance `/health` endpoint in `backend/app/main.py` to return:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "vault_connected": true,
  "timestamp": "2026-01-17T..."
}
```

Check vault connection status by attempting to load VaultManager config.

---

## Phase 8: Documentation

### 8.1 Create DEPLOY.md
Complete deployment guide including:
- Quick start for dev and prod
- Environment configuration
- Git workflow
- Makefile commands
- Docker Compose commands
- Traefik configuration
- Health check usage
- Monitoring
- Troubleshooting
- Security checklist
- CI/CD information

### 8.2 Update README.md
Add deployment section with quick start commands.

---

## Deliverables Checklist

Verify all items are complete:

- [ ] Dockerfile with multi-stage build (dev/prod targets)
- [ ] docker-compose.yml (base config)
- [ ] docker-compose.dev.yml (dev overrides with Traefik labels for memory-dev.example.com)
- [ ] docker-compose.prod.yml (prod overrides with Traefik labels for memory.example.com)
- [ ] .env.example template
- [ ] .env.dev.example and .env.prod.example templates
- [ ] .gitignore updated
- [ ] Makefile with dev/prod/build/logs commands
- [ ] docker-entrypoint.sh
- [ ] Health check endpoint implemented
- [ ] .github/workflows/ci.yml (test + deploy)
- [ ] .github/workflows/docker-publish.yml (GHCR)
- [ ] DEPLOY.md documentation
- [ ] Git branches created (dev, main)
- [ ] Dev environment tested and accessible at https://memory-dev.example.com
- [ ] Prod environment tested and accessible at https://memory.example.com

---

## Testing Instructions

After setup, test the deployment:

### Development Testing
```bash
# 1. Setup environment
cp .env.dev.example .env.dev
# Edit .env.dev with your values

# 2. Ensure proxy network exists
docker network create proxy || echo "proxy network already exists"

# 3. Start development environment
make dev

# 4. Verify health
make health-dev
# Or: curl http://localhost:8766/health

# 5. Check Traefik routing
# Access https://memory-dev.example.com/health
```

### Production Testing
```bash
# 1. Setup environment
cp .env.prod.example .env.prod
# Edit .env.prod with production values
# IMPORTANT: Set REQUIRE_AUTH=true and strong API_TOKEN

# 2. Start production environment
make prod

# 3. Verify health
make health
# Or: curl http://localhost:8765/health

# 4. Check Traefik routing
# Access https://memory.example.com/health
```

---

## Traefik Requirements

The deployment assumes:
- Traefik is running and accessible
- `proxy` network exists (external)
- Cloudflare DNS resolver configured
- Domains configured:
  - `memory-dev.example.com` → points to Traefik
  - `memory.example.com` → points to Traefik

If Traefik is not available, modify the compose files to:
- Remove Traefik labels
- Use direct port mapping
- Use internal network instead of external proxy network

---

## Output Format

When complete, output:
```
<promise>DEPLOYMENT_COMPLETE</promise>

Status:
- Dev: https://memory-dev.example.com (ready/tested)
- Prod: https://memory.example.com (ready/tested)
```

If testing cannot be completed (e.g., Docker/Traefik not available), note:
```
<promise>DEPLOYMENT_COMPLETE</promise>

Status:
- Dev: https://memory-dev.example.com (infrastructure ready, testing requires Docker/Traefik)
- Prod: https://memory.example.com (infrastructure ready, testing requires Docker/Traefik)
```

---

## Notes

- The unified Dockerfile builds the backend service (FastAPI)
- Port 8765 is used internally, 8766 for dev direct access
- All environment variables should be documented in .env.example
- Health check uses curl (included in Dockerfile)
- Entrypoint script handles environment-specific logic
- Makefile provides convenient commands for common operations
