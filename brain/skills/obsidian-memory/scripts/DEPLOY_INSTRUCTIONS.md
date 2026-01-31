# 🚀 Claude.ai MCP Server Deployment

## Quick Deploy (Recommended)

SSH to your server and run these commands:

```bash
# 1. SSH to server
ssh redleif-dev

# 2. Go to Obsidian Memory directory
cd /home/redleif/Obsidian-Memory/brain/skills/obsidian-memory/scripts/

# 3. Download files from this repo (or copy them manually)
# Copy all the new files to the server...

# 4. Run deployment
sudo ./quick-deploy.sh
```

## Manual File Copy

If you need to copy files manually, copy these files to the server:

**Files to copy to `/home/redleif/Obsidian-Memory/brain/skills/obsidian-memory/scripts/`:**

1. `claude-ai-mcp-server.js` - Main OAuth + MCP server
2. `claude-ai-mcp.service` - Systemd service file
3. `quick-deploy.sh` - Deployment script
4. `test-claude-ai-oauth.sh` - Testing utility

## What the deployment does:

1. ✅ Installs Node.js dependencies
2. ✅ Creates environment configuration
3. ✅ Stops old MCP server
4. ✅ Installs new Claude.ai compatible server
5. ✅ Updates nginx with OAuth endpoints
6. ✅ Starts and enables service
7. ✅ Tests OAuth endpoints

## After Deployment

### Test the server:
```bash
./test-claude-ai-oauth.sh
```

### Check service status:
```bash
sudo systemctl status claude-ai-mcp
```

### View logs:
```bash
sudo journalctl -u claude-ai-mcp -f
```

## Connect in Claude.ai

1. **Settings** → **Connectors** → **Add custom connector**
2. **Name**: `Obsidian Memory`
3. **URL**: `https://memory.redleif.dev/mcp`
4. **OAuth Client ID/Secret**: *Leave blank* (uses dynamic registration)
5. Click **Connect**

Claude.ai will automatically:
- Discover OAuth endpoints
- Register as a client
- Complete PKCE OAuth flow
- Connect to your memory vault

## Available Tools

Once connected, you'll have these tools in Claude.ai:

- **`mem_search`** - Search your memory vault
- **`mem_read`** - Read specific files
- **`mem_write`** - Write/update files

## Endpoints Available

- **OAuth Discovery**: `https://memory.redleif.dev/.well-known/oauth-authorization-server`
- **Client Registration**: `https://memory.redleif.dev/register`
- **Authorization**: `https://memory.redleif.dev/authorize`
- **Token Exchange**: `https://memory.redleif.dev/token`
- **MCP Protocol**: `https://memory.redleif.dev/mcp`

## Troubleshooting

If connection fails:
1. Check service: `sudo systemctl status claude-ai-mcp`
2. Check logs: `sudo journalctl -u claude-ai-mcp -f`
3. Test endpoints: `./test-claude-ai-oauth.sh`
4. Verify nginx: `sudo nginx -t && sudo systemctl reload nginx`

Ready to deploy! 🎉