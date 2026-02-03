# Troubleshooting Guide

Common issues and solutions for Obsidian-Memory.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Connection Issues](#connection-issues)
- [Authentication Issues](#authentication-issues)
- [MCP Server Issues](#mcp-server-issues)
- [Backend API Issues](#backend-api-issues)
- [Vault Issues](#vault-issues)
- [Performance Issues](#performance-issues)
- [Docker Issues](#docker-issues)

## Installation Issues

### Bun Not Found

**Symptom**: `bun: command not found`

**Solution**:
```bash
# Install Bun
curl -fsSL https://bun.sh/install | bash

# Add to PATH
echo 'export PATH="$HOME/.bun/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify installation
bun --version
```

### Python Version Mismatch

**Symptom**: `Python 3.11+ required`

**Solution**:
```bash
# Check Python version
python --version

# Install Python 3.11+ via pyenv
pyenv install 3.11
pyenv local 3.11

# Or use system package manager
sudo apt install python3.11  # Ubuntu/Debian
brew install python@3.11      # macOS
```

### Pip Installation Fails

**Symptom**: `pip install -e ".[dev]"` fails

**Solution**:
```bash
# Upgrade pip
pip install --upgrade pip setuptools wheel

# Use virtual environment
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Connection Issues

### Cannot Connect to Backend

**Symptom**: `Connection refused` or `Network error`

**Diagnostic**:
```bash
# Check if backend is running
curl http://localhost:8765/health

# Check port binding
netstat -tulpn | grep 8765

# Check Docker container status
docker ps | grep memory

# View backend logs
docker logs memory
```

**Solutions**:
```bash
# Restart backend
docker restart memory

# Check firewall rules
sudo ufw status
sudo ufw allow 8765/tcp

# Verify environment variables
docker exec memory env | grep -E "HOST|PORT"
```

### Cannot Connect to MCP Server

**Symptom**: Claude.ai or Cursor cannot connect

**Diagnostic**:
```bash
# Check MCP server health
curl http://localhost:3000/health

# For remote access
curl https://memory.redleif.dev/mcp/health

# Check container status
docker ps | grep mcp

# View MCP logs
docker logs memory-mcp
```

**Solutions**:
```bash
# Restart MCP server
docker restart memory-mcp

# Check environment variables
docker exec memory-mcp env | grep MCP

# Verify network connectivity
docker network inspect proxy
```

### CORS Errors

**Symptom**: Browser console shows CORS errors

**Solution**:
```bash
# Enable CORS in backend
export CORS_ENABLED=true
export CORS_ALLOWED_ORIGINS="https://yourdomain.com,https://claude.ai"

# Or in docker-compose.yml:
environment:
  - CORS_ENABLED=true
  - CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://claude.ai
```

## Authentication Issues

### 401 Unauthorized

**Symptom**: `401 Unauthorized` on API requests

**Diagnostic**:
```bash
# Check if auth is required
curl http://localhost:8765/health

# Test with Bearer token
curl -H "Authorization: Bearer your-token" \
     http://localhost:8765/api/notes
```

**Solutions**:
```bash
# Disable auth for development
export REQUIRE_AUTH=false

# Or set correct token
export API_TOKEN=your-secure-token

# Verify token in Docker
docker exec memory env | grep API_TOKEN
```

### 403 Forbidden (Cloudflare Access)

**Symptom**: `403 Forbidden` with Cloudflare Access enabled

**Diagnostic**:
```bash
# Check Cloudflare Access configuration
curl -I https://memory.redleif.dev/health

# View Cloudflare Access logs
# (Cloudflare Zero Trust dashboard → Logs)
```

**Solutions**:
1. Verify email is in Cloudflare Access policy
2. Check `CLOUDFLARE_ACCESS_TEAM_DOMAIN` environment variable
3. Ensure JWT header is being forwarded by Traefik
4. Test authentication flow:
   ```bash
   # Browser should redirect to Cloudflare login
   open https://memory.redleif.dev/api/notes
   ```

### OAuth Token Expired

**Symptom**: `Token expired` or `Invalid token`

**Solution**:
1. Disconnect from Claude.ai: Settings → Integrations → Obsidian-Memory → Disconnect
2. Reconnect and re-authenticate
3. Verify token expiration settings in Cloudflare Access

### Invalid OAuth Credentials

**Symptom**: `Invalid client credentials`

**Solution**:
```bash
# Verify Client ID matches Cloudflare Access application
echo $CLOUDFLARE_OAUTH_CLIENT_ID

# Check authorization and token URLs
echo $CLOUDFLARE_ACCESS_TEAM_DOMAIN

# Correct format:
# https://your-team.cloudflareaccess.com/cdn-cgi/access/authorize
# https://your-team.cloudflareaccess.com/cdn-cgi/access/token
```

## MCP Server Issues

### MCP Server Won't Start

**Symptom**: MCP server exits immediately

**Diagnostic**:
```bash
# View full logs
docker logs memory-mcp --tail 100

# Check environment variables
docker exec memory-mcp env

# Test manually
docker exec -it memory-mcp bun run src/index.ts
```

**Solutions**:
```bash
# Verify Bun installation
docker exec memory-mcp bun --version

# Check for syntax errors
docker exec memory-mcp bun run typecheck

# Rebuild container
docker-compose build memory-mcp
docker-compose up -d memory-mcp
```

### MCP Tools Not Available

**Symptom**: No tools listed in Claude.ai or Cursor

**Diagnostic**:
```bash
# Test tool discovery
curl https://memory.redleif.dev/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

**Solutions**:
1. Verify MCP server is running
2. Check backend API is accessible from MCP server
3. Ensure tools are properly registered in MCP server code
4. Restart MCP server: `docker restart memory-mcp`

### SSE Connection Drops

**Symptom**: Connection closes unexpectedly

**Solutions**:
```bash
# Increase timeout in reverse proxy (Traefik)
# In labels:
- "traefik.http.services.memory-mcp.loadbalancer.server.timeouts.read=300s"

# Enable keepalive in backend
# In backend config:
KEEPALIVE_TIMEOUT=300

# Check for network interruptions
ping memory.redleif.dev
```

## Backend API Issues

### Database Empty (0 Notes)

**Symptom**: `/health` shows `vault_connected: false` or 0 notes

**Diagnostic**:
```bash
# Check vault path
docker exec memory env | grep VAULT_PATH

# Verify vault directory exists
docker exec memory ls -la /vaults

# Check permissions
docker exec memory ls -la /vaults/your-vault
```

**Solutions**:
```bash
# Fix permissions (container runs as UID 1000)
sudo chown -R 1000:1000 /path/to/vaults

# Verify vault mount in docker-compose.yml
volumes:
  - /home/user/vaults:/vaults:rw  # Note: :rw for read-write

# Register vault via API
curl -X POST http://localhost:8765/api/vaults \
  -H "Content-Type: application/json" \
  -d '{"name": "my-vault", "path": "/vaults/my-vault"}'

# Trigger reindex
curl -X POST http://localhost:8765/api/vaults/my-vault/reindex
```

### AI Features Not Working

**Symptom**: Session summaries fail, entity extraction doesn't work

**Diagnostic**:
```bash
# Check API key
docker exec memory env | grep ANTHROPIC_API_KEY

# Test Claude API
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-sonnet-20240229","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'
```

**Solutions**:
```bash
# Set API key
export ANTHROPIC_API_KEY=your-api-key

# In Docker:
docker-compose down
# Edit .env or docker-compose.yml to add ANTHROPIC_API_KEY
docker-compose up -d

# Verify
docker exec memory env | grep ANTHROPIC_API_KEY
```

### Rate Limit Errors

**Symptom**: `429 Too Many Requests`

**Solutions**:
```bash
# Increase rate limits
export RATE_LIMIT_REQUESTS_PER_MINUTE=120
export RATE_LIMIT_BURST=20

# Or disable rate limiting (dev only)
export RATE_LIMIT_ENABLED=false

# Check current limits
curl -I http://localhost:8765/api/notes
# Look for X-RateLimit-* headers
```

### Slow API Responses

**Symptom**: Requests take several seconds

**Diagnostic**:
```bash
# Check response time
time curl http://localhost:8765/api/notes

# View metrics
curl http://localhost:8765/metrics

# Check logs for slow queries
docker logs memory | grep -i slow
```

**Solutions**:
1. Rebuild FTS5 index: `POST /api/search/reindex`
2. Optimize database: `POST /api/vaults/{vault}/optimize`
3. Increase container resources:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 1G
         cpus: '1.0'
   ```
4. Add database indexes (if using PostgreSQL)

## Vault Issues

### Vault Not Writable

**Symptom**: `Permission denied` when writing notes

**Solution**:
```bash
# Check ownership
ls -la /path/to/vault

# Fix ownership (container UID is 1000)
sudo chown -R 1000:1000 /path/to/vault

# Verify mount is read-write
docker inspect memory | grep -A 5 Mounts
# Should show "RW": true
```

### Git Sync Fails

**Symptom**: Sync operations return errors

**Diagnostic**:
```bash
# Check git status
docker exec memory git -C /vaults/my-vault status

# Check remote
docker exec memory git -C /vaults/my-vault remote -v
```

**Solutions**:
```bash
# Initialize git repo
curl -X POST http://localhost:8765/api/sync/init/my-vault

# Add remote
curl -X POST "http://localhost:8765/api/sync/remote/my-vault?url=https://github.com/user/repo.git"

# Test connectivity
docker exec memory git -C /vaults/my-vault fetch --dry-run
```

### Wikilinks Not Working

**Symptom**: `[[wikilinks]]` not creating graph edges

**Diagnostic**:
```bash
# Check graph
curl http://localhost:8765/api/graph

# View edges
curl http://localhost:8765/api/graph/edges
```

**Solutions**:
1. Ensure notes use standard wikilink format: `[[note-title]]`
2. Verify frontmatter is valid YAML
3. Trigger graph rebuild: `POST /api/graph/rebuild`
4. Check note permalinks match wikilink targets

## Performance Issues

### High Memory Usage

**Symptom**: Container uses excessive memory

**Diagnostic**:
```bash
# Check container stats
docker stats memory

# View process memory
docker exec memory ps aux
```

**Solutions**:
```bash
# Set memory limit
# In docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 512M
    reservations:
      memory: 256M

# Restart container
docker restart memory
```

### High CPU Usage

**Symptom**: CPU usage consistently high

**Diagnostic**:
```bash
# Check what's running
docker exec memory top

# View logs for errors
docker logs memory --tail 100
```

**Solutions**:
1. Check for infinite loops in logs
2. Optimize FTS5 queries (add LIMIT clauses)
3. Reduce AI API call frequency
4. Set CPU limit in docker-compose.yml

### Slow Search

**Symptom**: Search queries take > 1 second

**Solutions**:
```bash
# Rebuild FTS5 index
curl -X POST http://localhost:8765/api/search/reindex

# Vacuum database
curl -X POST http://localhost:8765/api/admin/vacuum

# Use more specific queries (avoid wildcards)
```

## Docker Issues

### Container Won't Start

**Symptom**: `docker-compose up` fails

**Diagnostic**:
```bash
# View full logs
docker-compose logs

# Check for port conflicts
netstat -tulpn | grep -E "8765|3000"

# Verify Docker version
docker --version
docker-compose --version
```

**Solutions**:
```bash
# Remove old containers
docker-compose down -v
docker-compose up -d

# Rebuild images
docker-compose build --no-cache
docker-compose up -d

# Check disk space
df -h
```

### Image Pull Fails

**Symptom**: Cannot pull from ghcr.io

**Solutions**:
```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Or use personal access token
docker login ghcr.io

# Pull manually
docker pull ghcr.io/jodfie/obsidian-memory:latest
```

### Volume Mount Issues

**Symptom**: Files not accessible in container

**Diagnostic**:
```bash
# Check mounts
docker inspect memory | grep -A 10 Mounts

# Test from inside container
docker exec memory ls -la /vaults
```

**Solutions**:
```bash
# Verify host path exists
ls -la /path/to/vaults

# Check SELinux (if applicable)
ls -Z /path/to/vaults

# Fix SELinux context
sudo chcon -Rt svirt_sandbox_file_t /path/to/vaults

# Use absolute paths in docker-compose.yml
volumes:
  - /absolute/path/to/vaults:/vaults:rw
```

## Logging and Debugging

### Enable Debug Logging

```bash
# Set environment variables
export DEBUG=true
export LOG_LEVEL=DEBUG

# Or in docker-compose.yml:
environment:
  - DEBUG=true
  - LOG_LEVEL=DEBUG

# Restart containers
docker-compose restart
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker logs -f memory
docker logs -f memory-mcp

# Last N lines
docker logs --tail 100 memory

# Since timestamp
docker logs --since 10m memory
```

### Log Files

```bash
# Backend logs
tail -f ~/.obsidian-memory/logs/obsidian-memory.log

# MCP server logs
docker logs memory-mcp

# System logs
journalctl -u docker -f
```

## Getting Help

If none of these solutions work:

1. **Gather diagnostic information**:
   ```bash
   # Create diagnostic report
   cat > diagnostic-report.txt <<EOF
   # System Info
   $(uname -a)
   $(docker --version)
   $(docker-compose --version)

   # Container Status
   $(docker ps -a)

   # Logs (last 50 lines)
   $(docker logs --tail 50 memory 2>&1)
   $(docker logs --tail 50 memory-mcp 2>&1)

   # Environment
   $(docker exec memory env | grep -v SECRET | grep -v TOKEN | grep -v KEY)
   EOF
   ```

2. **Open GitHub Issue**: https://github.com/jodfie/Obsidian-Memory/issues
   - Include diagnostic report
   - Describe expected vs actual behavior
   - List steps to reproduce

3. **Check existing issues**: Search for similar problems

4. **Review documentation**:
   - [Architecture Guide](ARCHITECTURE.md)
   - [API Documentation](api.md)
   - [Deployment Guide](deployment.md)

## Common Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| `Connection refused` | Service not running | Start service |
| `Permission denied` | Wrong file permissions | Fix with `chown` |
| `401 Unauthorized` | Missing/invalid auth | Check token/credentials |
| `403 Forbidden` | Not allowed | Check access policy |
| `404 Not Found` | Resource doesn't exist | Verify ID/path |
| `429 Too Many Requests` | Rate limited | Wait or increase limits |
| `500 Internal Server Error` | Server bug | Check logs |
| `503 Service Unavailable` | Dependency down | Check backend/AI API |

## Prevention Tips

### Regular Maintenance

```bash
# Weekly
- Review logs for errors
- Check disk space
- Update containers: docker-compose pull && docker-compose up -d

# Monthly
- Rotate logs
- Vacuum database: POST /api/admin/vacuum
- Review and clean old sessions

# As Needed
- Backup vault data
- Test restore procedures
- Update dependencies
```

### Monitoring

Set up monitoring for:
- Container health: `docker ps`
- Disk space: `df -h`
- API health: `/health` endpoint
- Error rates in logs

### Backups

```bash
# Backup vault
tar -czf vault-backup-$(date +%Y%m%d).tar.gz /path/to/vault

# Backup database (if not using SQLite)
docker exec memory pg_dump obsidian_memory > backup.sql

# Automate with cron
0 2 * * * /path/to/backup-script.sh
```
