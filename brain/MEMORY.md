# MEMORY.md - Long-Term Memory

## System Insights

### Discord Integration Issues (Jan 2026)
- **Channel ID Problem**: 618649027126362122 returns "Unknown Channel" errors
- **Root Cause**: Configured Discord channels in usage-stats-config.json are invalid
- **Workaround**: Using sessions_send to main session for stats delivery
- **Action Needed**: Jody needs to provide correct Discord channel IDs for usage stats

### Session Management Patterns
- **Alert Threshold**: 100k tokens = warning, 150k = extract context to memory
- **Reset Pattern**: Main session reset at 168k tokens (Jan 25) - system handled gracefully
- **Context Extraction**: Before resets, preserve key decisions, config changes, preferences
- **Monitoring Frequency**: Cron jobs check every 30 minutes during active hours

### Tool Preferences
- **Cloudflare**: Always use cloudflare-api skill for DNS, tunnels, zones
- **Memory**: Write significant events to daily files, distill to MEMORY.md
- **Sessions**: Use sessions_send for cross-session communication

### 🚨 CRITICAL DEPLOYMENT DIRECTIVE (Jan 27, 2026)
**DEPLOY EVERYTHING MYSELF ON THE SERVER UNLESS OTHERWISE SPECIFIED**
- **Default**: Deploy directly to redleif-dev server myself using exec/ssh
- **No Scripts for Jody**: Don't create install/implementation scripts for him to run
- **Script Usage**: Can make scripts for my own usage, but clean up afterwards
- **Exception**: Only create user scripts when explicitly requested
- **Apply Immediately**: This applies to all deployments going forward
- **Heartbeats**: Rotate maintenance tasks, avoid token burn

## User Context

### Jody's Work Style & Preferences
- **ADHD-optimized**: External memory systems, next-action focus, anti-planner approach
- **Platform Behavior**: Mobile = concise responses + auto reminders, Desktop = full technical depth
- **Tech Stack**: Apple ecosystem, homelab at redleif.dev, Enhanced Obsidian-Memory MCP server
- **Projects**: Obsidian-Memory (current focus), TechKB, CoparentingSystem, GaScanner
- **Time Zone**: Eastern (Georgia)
- **ADHD Support Modes**: Task breakdown, executive function support, hyperfocus-friendly responses
- **Location**: Georgia (Savannah area), Crime analyst at SARIC

### Platform Detection Patterns
- **Mobile indicators**: Short queries, quick logging tasks, CPS expenses, custody documentation
- **Desktop indicators**: Deep technical work, infrastructure tasks, training material development
- **Default assumption**: MOBILE unless context suggests otherwise

### Enhanced Obsidian-Memory Integration
- **Server**: http://memory.redleif.dev (813 notes indexed)
- **Workflow**: Always mem_search first, use graph navigation, create with mem_write
- **Projects**: TechKB structure (numbered folders), CPS organization (role-based folders)
- **Critical**: Use Enhanced MCP server, not BasicMemory

### Current Projects (Jan 2026)
- **Obsidian-Memory**: Unified AI memory system integration
- **Discord Stats**: Automated usage monitoring via cron jobs
- **Infrastructure**: VPS hosting multiple services (Paperless, n8n, etc.)

---
*Last updated: 2026-01-27 4:30 PM EST*