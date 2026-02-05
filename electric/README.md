# ElectricSQL Deployment on Fly.io

This directory contains the deployment configuration for ElectricSQL sync service on Fly.io.

## Prerequisites

1. **Fly.io CLI** - Install flyctl
   ```bash
   # macOS
   brew install flyctl

   # Linux
   curl -L https://fly.io/install.sh | sh

   # Windows
   pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"
   ```

2. **Fly.io Account** - Sign up and authenticate
   ```bash
   fly auth signup    # or fly auth login
   ```

3. **Supabase Project** - You need an existing Supabase project with:
   - Database schema applied (see `supabase/migrations/`)
   - Logical replication enabled (enabled by default)

## Getting Your Supabase Connection String

ElectricSQL requires a direct connection to your Supabase Postgres database.

### For Supabase Free Tier (IPv6)

Fly.io supports IPv6, so you can use the free tier without issues.

1. Go to your Supabase Dashboard
2. Navigate to **Project Settings** > **Database**
3. Under **Connection string**, select **URI**
4. Copy the connection string (looks like):
   ```
   postgresql://postgres.[project-ref]:[password]@db.[project-ref].supabase.co:5432/postgres
   ```

**Important Notes:**
- Do NOT use the pooler connection string (the one with `pooler.supabase.com`)
- The password is your database password set during project creation
- If you forgot your password, reset it in **Project Settings** > **Database** > **Database password**

### For Supabase Pro (IPv4)

If you're on Supabase Pro with a dedicated IPv4 address, use the direct connection string from your dashboard.

## Deployment Steps

### 1. Create the Fly.io App

```bash
cd electric
fly apps create obsidian-memory-electric
```

### 2. Set the Database Secret

```bash
# Replace with your actual Supabase connection string
fly secrets set DATABASE_URL="postgresql://postgres.[project-ref]:[password]@db.[project-ref].supabase.co:5432/postgres"
```

### 3. Deploy

```bash
fly deploy
```

### 4. Verify Deployment

Check the app status:
```bash
fly status
```

View logs:
```bash
fly logs
```

Test the health endpoint:
```bash
curl https://obsidian-memory-electric.fly.dev/v1/health
```

Test shape endpoint (should return empty array initially):
```bash
curl "https://obsidian-memory-electric.fly.dev/v1/shape?table=notes"
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Supabase Postgres connection string |
| `ELECTRIC_WRITE_TO_PG_MODE` | No | Write mode: `direct` (default) or `logical_replication` |
| `PG_PROXY_PORT` | No | PG proxy port (default: 65432) |
| `LOG_LEVEL` | No | Logging level: `debug`, `info`, `warning`, `error` |

### Scaling

Adjust resources in `fly.toml`:

```toml
[vm]
  memory = "1gb"     # Increase for larger datasets
  cpu_kind = "shared"
  cpus = 2           # More CPUs for concurrent connections
```

Scale to multiple regions:
```bash
fly scale count 2 --region iad,lax
```

## Custom Domain Setup

1. Add a CNAME record pointing to `obsidian-memory-electric.fly.dev`
2. Configure the certificate:
   ```bash
   fly certs add sync.memory.yourdomain.com
   ```

## Troubleshooting

### Connection Refused to Database

**Symptom:** Logs show connection errors to Supabase.

**Solutions:**
1. Verify DATABASE_URL is correct:
   ```bash
   fly secrets list
   ```
2. Check Supabase is not paused (free tier pauses after inactivity)
3. Ensure you're using the direct connection, not the pooler

### IPv6 Connection Issues

**Symptom:** Cannot connect from local machine to verify.

**Solution:** Local machines often don't have IPv6. Deploy to Fly.io first (which has IPv6), then test via the Fly.io URL.

### Electric Not Starting

**Symptom:** App crashes on startup.

**Solutions:**
1. Check logs for specific errors:
   ```bash
   fly logs --app obsidian-memory-electric
   ```
2. Verify DATABASE_URL format is correct
3. Ensure Supabase database password has no special URL characters (or URL-encode them)

### Shape Returns Empty Data

**Symptom:** `/v1/shape?table=notes` returns empty even though data exists.

**Solutions:**
1. Verify table exists in Supabase
2. Check if RLS policies are blocking access
3. Ensure logical replication is enabled on the table

### Health Check Failing

**Symptom:** Fly.io reports unhealthy instances.

**Solutions:**
1. Increase grace period in `fly.toml` health check
2. Check memory usage - may need more RAM
3. Review logs for errors during startup

## Monitoring

### View Logs
```bash
fly logs --app obsidian-memory-electric
```

### SSH into Container
```bash
fly ssh console --app obsidian-memory-electric
```

### Check Metrics
```bash
fly status --app obsidian-memory-electric
```

## Useful Commands

```bash
# Restart the app
fly apps restart obsidian-memory-electric

# View current secrets (names only)
fly secrets list

# Update a secret
fly secrets set DATABASE_URL="new-connection-string"

# Scale to zero (cost savings)
fly scale count 0

# Scale back up
fly scale count 1

# View app info
fly info

# Open app in browser
fly open
```

## References

- [ElectricSQL Documentation](https://electric-sql.com/docs)
- [ElectricSQL + Supabase Integration](https://electric-sql.com/docs/integrations/supabase)
- [Fly.io Documentation](https://fly.io/docs)
- [Supabase Connection Strings](https://supabase.com/docs/guides/database/connecting-to-postgres)
