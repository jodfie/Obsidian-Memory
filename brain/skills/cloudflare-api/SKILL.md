---
name: cloudflare
description: Connect to Cloudflare API for DNS management, tunnels, Access protection, and zone administration. Use when user needs to manage domains, DNS records, create tunnels, or set up Cloudflare Access security.
read_when:
  - User asks about Cloudflare DNS or domains
  - User wants to create or manage DNS records
  - User needs to set up Cloudflare tunnels
  - User wants to list their Cloudflare zones
  - User wants to protect applications with Cloudflare Access
  - User mentions authentication, SSO, or application protection
metadata:
  clawdbot:
    emoji: "☁️"
    requires:
      bins: ["curl", "jq"]
---

# Cloudflare Skill

Connect to [Cloudflare](https://cloudflare.com) API for DNS management, tunnels, Access protection, and zone administration.

## Setup

### 1. Get Your API Token
1. Go to [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens)
2. Create a token with required permissions:
   - **Zone:Read** - List domains
   - **DNS:Edit** - Manage DNS records
   - **Account:Cloudflare Tunnel:Edit** - Manage tunnels
   - **Account:Cloudflare Access:Edit** - Manage Access applications and policies
3. Copy the token

### 2. Configure
```bash
# Option A: Store in file (recommended)
echo "YOUR_API_TOKEN" > ~/.cloudflare_token
chmod 600 ~/.cloudflare_token

# Option B: Environment variable
export CLOUDFLARE_API_TOKEN="YOUR_API_TOKEN"
```

### 3. Test Connection
```bash
./scripts/setup.sh
```

---

## Commands

### Zones (Domains)

```bash
./scripts/zones/list.sh                    # List all zones
./scripts/zones/list.sh --json             # JSON output
./scripts/zones/get.sh example.com         # Get zone details
```

### DNS Records

```bash
# List records
./scripts/dns/list.sh example.com
./scripts/dns/list.sh example.com --type A
./scripts/dns/list.sh example.com --name api

# Create record
./scripts/dns/create.sh example.com \
  --type A \
  --name api \
  --content 1.2.3.4 \
  --proxied

# Create CNAME
./scripts/dns/create.sh example.com \
  --type CNAME \
  --name www \
  --content example.com \
  --proxied

# Update record
./scripts/dns/update.sh example.com \
  --name api \
  --type A \
  --content 5.6.7.8

# Delete record
./scripts/dns/delete.sh example.com --name api --type A
```

### Tunnels

```bash
# List tunnels
./scripts/tunnels/list.sh

# Create tunnel
./scripts/tunnels/create.sh my-tunnel

# Configure tunnel ingress
./scripts/tunnels/configure.sh my-tunnel \
  --hostname app.example.com \
  --service http://localhost:3000

# Get run token
./scripts/tunnels/token.sh my-tunnel

# Delete tunnel
./scripts/tunnels/delete.sh my-tunnel
```

### Access (Zero Trust)

```bash
# List Access applications
./scripts/access/list-apps.sh
./scripts/access/list-apps.sh --json

# List policies for an app
./scripts/access/list-policies.sh ABC123
./scripts/access/list-policies.sh ABC123 --json

# Create Access application
./scripts/access/create-app.sh example.com \
  --name "My App" \
  --subdomain app \
  --service http://localhost:3000

# Create Access policy
./scripts/access/create-policy.sh example.com \
  --app-id ABC123 \
  --name "Allow Team" \
  --email jody@example.com

# Policy with email domain (allow anyone @company.com)
./scripts/access/create-policy.sh example.com \
  --app-id ABC123 \
  --name "Allow Company" \
  --email-domain company.com

# Quick setup (app + policy)
./scripts/access/setup-protection.sh example.com app jody@example.com
./scripts/access/setup-protection.sh example.com "" jody@example.com  # root domain
```

---

## Token Permissions

| Feature | Required Permission |
|---------|-------------------|
| List zones | Zone:Read |
| Manage DNS | DNS:Edit |
| Manage tunnels | Account:Cloudflare Tunnel:Edit |
| Manage Access | Account:Cloudflare Access:Edit |

Create token at: [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens)

---

## Common Workflows

### Point subdomain to server
```bash
./scripts/dns/create.sh mysite.com --type A --name api --content 1.2.3.4 --proxied
```

### Set up tunnel for local service
```bash
# 1. Create tunnel
./scripts/tunnels/create.sh webhook-tunnel

# 2. Configure ingress
./scripts/tunnels/configure.sh webhook-tunnel \
  --hostname hook.mysite.com \
  --service http://localhost:8080

# 3. Add DNS record
TUNNEL_ID=$(./scripts/tunnels/list.sh --name webhook-tunnel --quiet)
./scripts/dns/create.sh mysite.com \
  --type CNAME \
  --name hook \
  --content ${TUNNEL_ID}.cfargotunnel.com \
  --proxied

# 4. Run tunnel
TOKEN=$(./scripts/tunnels/token.sh webhook-tunnel)
cloudflared tunnel run --token $TOKEN
```

### Protect application with Cloudflare Access
```bash
# Quick setup: creates app + policy in one command
./scripts/access/setup-protection.sh mysite.com app jody@example.com

# Manual setup for more control:
# 1. Create Access application
./scripts/access/create-app.sh mysite.com --name "My App" --subdomain app

# 2. Create policy (from output above)
./scripts/access/create-policy.sh mysite.com --app-id <APP_ID> --name "Allow Jody" --email jody@example.com

# Your app is now protected: https://app.mysite.com requires authentication
```

---

## Output Formats

| Flag | Description |
|------|-------------|
| `--json` | Raw JSON from API |
| `--table` | Formatted table (default) |
| `--quiet` | Minimal output (IDs only) |

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| "No API token found" | Run setup or set CLOUDFLARE_API_TOKEN |
| "401 Unauthorized" | Check token is valid |
| "403 Forbidden" | Token missing required permission |
| "Zone not found" | Verify domain is in your account |
