# Enhanced Cron Job with Memory Integration

## Current Cron Job Enhancement

The existing Clawdbot cron job can be enhanced to include Memory integration:

## Modified Cron Logic

```bash
#!/bin/bash
# Enhanced token monitor with Memory integration

# Check all sessions for token count
sessions=$(clawdbot sessions list --format=json)

for session in $sessions; do
    session_id=$(echo $session | jq -r '.sessionKey')
    token_count=$(echo $session | jq -r '.tokenCount // 0')
    
    # Warning at 80k tokens
    if [ "$token_count" -gt 80000 ] && [ "$token_count" -lt 95000 ]; then
        echo "⚠️ Session $session_id approaching limit: ${token_count} tokens"
    fi
    
    # Auto-summarize at 95k tokens
    if [ "$token_count" -gt 95000 ]; then
        echo "🧠 Auto-summarizing session $session_id (${token_count} tokens)"
        python3 /home/redleif/Obsidian-Memory/brain/scripts/session-memory-hook.py \
            --session-id "$session_id" \
            --token-count "$token_count"
        
        # Trigger session reset after successful summarization
        if [ $? -eq 0 ]; then
            echo "✅ Context preserved, resetting session"
            # clawdbot sessions reset --session-key "$session_id"
        fi
    fi
done
```

## Integration Points

1. **Existing cron** - Modify current 30-min cron job
2. **Memory hook** - Call Python script before reset
3. **Vault storage** - Store summaries in `memory/session-summaries/`
4. **Daily logs** - Update today's memory file with reset info

## Benefits

- **Zero context loss** - Important decisions preserved
- **Token efficiency** - Sessions reset before hitting limits  
- **Query capability** - "What did we decide about X?" searches vault
- **Automatic** - No manual intervention required

## Next Steps

1. Update existing cron job with Memory hooks
2. Test with a high-token session
3. Verify summaries are useful and searchable
4. Monitor effectiveness over next few days

This completes the token efficiency system with intelligent memory management.