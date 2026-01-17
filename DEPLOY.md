# Deployment Guide

Complete guide for deploying Obsidian-Memory in development and production environments.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Access to Traefik proxy network (named `proxy`)
- Domain configured: `memory-dev.redleif.dev` (dev) and `memory.redleif.dev` (prod)

## Quick Start

### Development Environment

1. **Setup environment file**
   ```bash
   cp .env.dev.example .env.dev
   # Edit .env.dev with your development values
   ```

2. **Start development environment**
   ```bash
   make dev
   # Or manually:
   # docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up -d --build
   ```

3. **Access the service**
   - URL: https://memory-dev.redleif.dev
   - Health check: https://memory-dev.redleif.dev/health
   - API docs: https://memory-dev.redleif.dev/docs

4. **View logs**
   ```bash
   make logs-dev
   ```

### Production Environment

1. **Setup environment file**
   ```bash
   cp .env.prod.example .env.prod
   # Edit .env.prod with production values and secrets
   # IMPORTANT: Set REQUIRE_AUTH=true and a strong API_TOKEN
   ```

2. **Start production environment**
   ```bash
   make prod
   # Or manually:
   # docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build
   ```

3. **Access the service**
   - URL: https://memory.redleif.dev
   - Health check: https://memory.redleif.dev/health
   - API docs: https://memory.redleif.dev/docs

4. **View logs**
   ```bash
   make logs-prod
   ```

## Environment Configuration

### Required Variables

- `BASIC_MEMORY_HOME` - Data directory (default: `/data`)
- `LOG_LEVEL` - Logging level (DEBUG/INFO/WARNING/ERROR)
- `VAULT_PATH` - Path to Obsidian vault (optional)

### Production Security

**CRITICAL**: In production, you MUST:

1. Set `REQUIRE_AUTH=true`
2. Set a strong `API_TOKEN` (use a password generator)
3. Configure `ANTHROPIC_API_KEY` if using AI features
4. Review all environment variables

### Example .env.prod

```bash
# Production Configuration
LOG_LEVEL=INFO
REQUIRE_AUTH=true
API_TOKEN=your-very-strong-random-token-here-minimum-32-characters
ANTHROPIC_API_KEY=sk-ant-...
BASIC_MEMORY_HOME=/data
VAULT_PATH=/vaults/prod-vault
```

## Git Workflow

### Development Flow

1. **Feature branches** → Merge to `dev`
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/my-feature
   # ... make changes ...
   git push origin feature/my-feature
   # Create PR to dev
   ```

2. **Auto-deploy to dev**
   - Merges to `dev` trigger CI/CD
   - Automatic deployment to development environment
   - Accessible at https://memory-dev.redleif.dev

### Production Flow

1. **Dev → Main** (requires manual approval)
   ```bash
   git checkout main
   git merge dev
   git push origin main
   ```

2. **Manual approval required**
   - GitHub Actions workflow requires manual approval
   - Deploys to production environment
   - Accessible at https://memory.redleif.dev

## Makefile Commands

```bash
# Setup
make setup          # Copy environment templates

# Development
make dev            # Start development environment
make logs-dev       # View development logs
make stop-dev        # Stop development environment
make restart-dev    # Restart development environment
make health-dev     # Check development health

# Production
make prod           # Start production environment
make logs-prod      # View production logs
make stop-prod      # Stop production environment
make restart-prod   # Restart production environment
make health         # Check production health

# Build
make build          # Build all images
make build-dev      # Build development image
make build-prod     # Build production image

# Cleanup
make clean          # Remove all containers, volumes, images
make clean-dev      # Clean development resources
make clean-prod     # Clean production resources
```

## Docker Compose Commands

### Development

```bash
# Start
docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up -d --build

# View logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

# Stop
docker compose -f docker-compose.yml -f docker-compose.dev.yml down

# Restart
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart
```

### Production

```bash
# Start
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build

# View logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Stop
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart
```

## Traefik Configuration

The deployment uses Traefik for reverse proxy and SSL termination. The configuration includes:

### Development Labels
- Router: `memory-dev`
- Domain: `memory-dev.redleif.dev`
- Entrypoint: `websecure`
- TLS: Cloudflare resolver

### Production Labels
- Router: `memory`
- Domain: `memory.redleif.dev`
- Entrypoint: `websecure`
- TLS: Cloudflare resolver
- Headers middleware for HTTPS

### Network Requirements

The `proxy` network must exist and be external:
```bash
docker network create proxy
```

Or if using Traefik's network:
```bash
docker network ls | grep proxy
```

## Health Check

The health endpoint provides:
- Status: `healthy` or `unhealthy`
- Version: Application version
- Vault connected: Whether vaults are configured
- Timestamp: Current UTC time

Example response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "vault_connected": true,
  "timestamp": "2026-01-17T03:30:00Z"
}
```

## Monitoring

### Health Endpoint
```bash
curl https://memory.redleif.dev/health
```

### Metrics Endpoint
```bash
curl https://memory.redleif.dev/metrics
```

### Logs
```bash
# Development
make logs-dev

# Production
make logs-prod

# Or directly
docker logs -f memory-dev
docker logs -f memory
```

## Troubleshooting

### Container won't start

1. Check logs:
   ```bash
   docker logs memory-dev
   ```

2. Check health:
   ```bash
   curl http://localhost:8765/health
   ```

3. Verify environment file:
   ```bash
   cat .env.dev
   ```

### Traefik routing issues

1. Verify network:
   ```bash
   docker network inspect proxy
   ```

2. Check container labels:
   ```bash
   docker inspect memory-dev | grep -A 10 Labels
   ```

3. Verify Traefik can see the container:
   - Check Traefik dashboard
   - Verify router configuration

### Port conflicts

If port 8765 or 8766 is in use:
```bash
# Check what's using the port
sudo lsof -i :8765
sudo lsof -i :8766

# Change ports in docker-compose files
```

### Permission issues

```bash
# Fix data directory permissions
sudo chown -R 1000:1000 /data
```

## Backup

### Data Volume

```bash
# Backup data volume
docker run --rm -v memory-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/memory-data-backup-$(date +%Y%m%d).tar.gz /data
```

### Vaults Volume

```bash
# Backup vaults volume
docker run --rm -v memory-vaults:/vaults -v $(pwd):/backup \
  alpine tar czf /backup/memory-vaults-backup-$(date +%Y%m%d).tar.gz /vaults
```

## Security Checklist

- [ ] `REQUIRE_AUTH=true` in production
- [ ] Strong `API_TOKEN` set (32+ characters)
- [ ] `ANTHROPIC_API_KEY` configured if using AI
- [ ] `.env.prod` not committed to git
- [ ] Traefik SSL/TLS configured
- [ ] Firewall rules configured
- [ ] Regular backups scheduled
- [ ] Log rotation configured
- [ ] Health checks passing
- [ ] Non-root user in containers

## CI/CD

### Automatic Deployment

- **Dev branch**: Auto-deploys to development on merge
- **Main branch**: Requires manual approval for production

### Manual Deployment

If CI/CD is not configured, deploy manually:

```bash
# On server
cd /path/to/obsidian-memory
git pull origin dev  # or main
make prod  # or make dev
```

## Support

For issues or questions:
- Check logs: `make logs-dev` or `make logs-prod`
- Health check: `make health`
- Review this documentation
- Check GitHub Issues
