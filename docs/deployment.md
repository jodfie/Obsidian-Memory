# Deployment Guide

Complete guide for deploying Obsidian-Memory in production.

## Docker Deployment

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+

### Quick Start

```bash
# Clone repository
git clone https://github.com/jodfie/Obsidian-Memory.git
cd Obsidian-Memory

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Environment Configuration

Create a `.env` file in the project root:

```bash
# Backend
API_TITLE=Obsidian-Memory
LOG_LEVEL=INFO
REQUIRE_AUTH=true
API_TOKEN=your-secure-token-here
ANTHROPIC_API_KEY=your-anthropic-key-here

# MCP Server
MCP_TRANSPORT=stdio
OBSIDIAN_MEMORY_API_URL=http://backend:8000
OBSIDIAN_MEMORY_API_TOKEN=your-secure-token-here

# Web UI
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Update `docker-compose.yml` to use environment file:

```yaml
services:
  backend:
    env_file:
      - .env
  # ... other services
```

### Volumes

The `obsidian-memory-data` volume stores:
- Vault configurations (`~/.obsidian-memory/config.json`)
- Search index (`~/.obsidian-memory/index.db`)
- Sync state (`~/.obsidian-memory/sync_state.json`)
- Logs (`~/.obsidian-memory/logs/`)

To persist data, mount a host directory:

```yaml
volumes:
  obsidian-memory-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /path/to/persistent/data
```

### Building Images

```bash
# Build all images
docker-compose build

# Build specific service
docker-compose build backend

# Build with no cache
docker-compose build --no-cache
```

### Health Checks

All services include health checks:

```bash
# Check service health
docker-compose ps

# View health check logs
docker inspect obsidian-memory-backend | grep -A 10 Health
```

## Manual Deployment

### Backend (FastAPI)

1. **Install dependencies**
   ```bash
   cd backend
   pip install -e ".[dev]"
   ```

2. **Configure**
   - Create `~/.obsidian-memory/config.json`
   - Set environment variables

3. **Run with uvicorn**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. **Run with systemd** (production)
   Create `/etc/systemd/system/obsidian-memory.service`:
   ```ini
   [Unit]
   Description=Obsidian-Memory Backend
   After=network.target

   [Service]
   Type=simple
   User=obsidian
   WorkingDirectory=/opt/obsidian-memory/backend
   Environment="PATH=/opt/obsidian-memory/venv/bin"
   ExecStart=/opt/obsidian-memory/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

### MCP Server

1. **Install Bun**
   ```bash
   curl -fsSL https://bun.sh/install | bash
   ```

2. **Install dependencies**
   ```bash
   cd mcp-server
   bun install
   ```

3. **Run**
   ```bash
   bun run src/index.ts
   ```

### Web UI

1. **Install dependencies**
   ```bash
   cd web-ui
   npm ci
   ```

2. **Build**
   ```bash
   npm run build
   ```

3. **Run production server**
   ```bash
   npm start
   ```

4. **Run with PM2** (production)
   ```bash
   npm install -g pm2
   pm2 start npm --name "obsidian-memory-web" -- start
   ```

## Reverse Proxy (Nginx)

Example Nginx configuration:

```nginx
server {
    listen 80;
    server_name obsidian-memory.example.com;

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Web UI
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8000/health;
    }
}
```

## SSL/TLS

### Let's Encrypt with Certbot

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d obsidian-memory.example.com

# Auto-renewal
sudo certbot renew --dry-run
```

## Security Best Practices

1. **Enable Authentication**
   ```bash
   REQUIRE_AUTH=true
   API_TOKEN=<strong-random-token>
   ```

2. **Use HTTPS**
   - Configure reverse proxy with SSL
   - Use Let's Encrypt for free certificates

3. **Firewall Rules**
   ```bash
   # Allow only necessary ports
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

4. **Non-Root Containers**
   - Docker containers run as non-root users
   - Ensure proper file permissions

5. **Secrets Management**
   - Use environment variables or secret management tools
   - Never commit secrets to repository
   - See [secret-management-best-practices.md](secret-management-best-practices.md)

## Monitoring

### Logs

Logs are stored in `~/.obsidian-memory/logs/obsidian-memory.log`:
- Structured JSON format
- Automatic rotation (10MB files, 5 backups)
- Configurable log level via `LOG_LEVEL`

### Metrics

Monitor the `/metrics` endpoint:
```bash
curl http://localhost:8000/metrics
```

### Health Checks

```bash
# Health endpoint
curl http://localhost:8000/health

# Docker health
docker inspect obsidian-memory-backend | grep Health
```

## Backup

### Vault Data

Vaults are stored as markdown files. Backup the vault directories:

```bash
# Backup vaults
tar -czf vaults-backup-$(date +%Y%m%d).tar.gz /path/to/vaults
```

### Database

Backup the SQLite index:
```bash
# Backup index
cp ~/.obsidian-memory/index.db ~/.obsidian-memory/index.db.backup
```

### Configuration

Backup configuration files:
```bash
# Backup config
cp ~/.obsidian-memory/config.json ~/.obsidian-memory/config.json.backup
cp ~/.obsidian-memory/sync_state.json ~/.obsidian-memory/sync_state.json.backup
```

## Scaling

### Horizontal Scaling

The backend is stateless (except for SQLite index). For horizontal scaling:

1. Use external database (PostgreSQL) instead of SQLite
2. Use shared storage for vaults (NFS, S3, etc.)
3. Use load balancer (Nginx, HAProxy)

### Vertical Scaling

Increase resources:
- CPU: More workers for uvicorn
- Memory: Increase container limits
- Storage: Larger volumes for vaults

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs backend
docker-compose logs mcp-server
docker-compose logs web-ui

# Check health
docker-compose ps
```

### Permission Issues

```bash
# Fix permissions
sudo chown -R $USER:$USER ~/.obsidian-memory
```

### Port Conflicts

```bash
# Check what's using ports
sudo lsof -i :8000
sudo lsof -i :3000

# Change ports in docker-compose.yml
```

### Database Locked

SQLite can have locking issues. Restart the backend service:

```bash
docker-compose restart backend
```

## Production Checklist

- [ ] Enable authentication (`REQUIRE_AUTH=true`)
- [ ] Set strong `API_TOKEN`
- [ ] Configure `ANTHROPIC_API_KEY` for AI features
- [ ] Set up SSL/TLS certificates
- [ ] Configure reverse proxy
- [ ] Set up log rotation
- [ ] Configure backups
- [ ] Set up monitoring/alerting
- [ ] Review firewall rules
- [ ] Test health checks
- [ ] Test authentication
- [ ] Test sync functionality
- [ ] Document vault locations
- [ ] Set up Git sync remotes
