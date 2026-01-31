# Token Monitor Integration with Obsidian-Memory

## Auto-Summarization Workflow

When sessions approach 100k tokens, this integration will:

1. **Detect threshold** - Monitor session token count via cron
2. **Extract key context** - Summarize decisions, discoveries, configurations 
3. **Store in Memory** - Write structured summary to Obsidian-Memory vault
4. **Reset session** - Trigger context reset to fresh state
5. **Enable queries** - Future sessions can query stored context instead of carrying bloat

## Implementation Points

### Cron Enhancement
- Monitor all sessions every 30min
- Alert at 80k tokens (warning)
- Auto-summarize at 95k tokens (action)
- Force reset at 100k tokens (limit)

### Memory Storage Pattern
```markdown
# Session Summary YYYY-MM-DD HH:mm

## Context
- **Session:** [session_id] 
- **Duration:** [duration]
- **Token count:** [tokens]
- **Channel:** [discord/cli/etc]

## Key Decisions
- [Decision 1 with rationale]
- [Decision 2 with rationale]

## Important Discoveries
- [Discovery 1]
- [Discovery 2]

## Configuration Changes
- [File]: [change made]
- [File]: [change made]

## Next Actions
- [Action item 1]
- [Action item 2]

## Context Links
- Related: [[other-session-summary]]
- Project: [[project-name]]
```

### Query Integration
- Before major changes: Query "What did we decide about X?"
- On session start: Check for related recent summaries
- During heartbeats: Review recent session summaries for followup

## Files to Create
1. `cron-token-monitor.sh` - Enhanced monitoring with Memory hooks
2. `summarize-session.py` - Extract and structure session context
3. `query-memory.py` - Search stored summaries for decisions/context

This transforms reactive token management into proactive knowledge management.