#!/usr/bin/env python3
"""
Session Memory Hook - Auto-summarize sessions before reset

Integrates with Clawdbot's token monitoring to:
1. Extract key context from high-token sessions
2. Store structured summaries in Obsidian-Memory vault
3. Enable future context queries without session bloat

Usage:
  python3 session-memory-hook.py --session-id <id> --token-count <count>
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
import subprocess
import argparse

def get_session_context(session_id):
    """Extract key context from a session via clawdbot API"""
    try:
        # Use clawdbot sessions history to get session content
        result = subprocess.run([
            'clawdbot', 'sessions', 'history', 
            '--session-key', session_id,
            '--limit', '50',
            '--format', 'json'
        ], capture_output=True, text=True, check=True)
        
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Failed to get session context: {e}", file=sys.stderr)
        return None

def extract_key_points(session_data):
    """Extract decisions, discoveries, and changes from session"""
    if not session_data:
        return {}
    
    # Simple keyword-based extraction (can be enhanced with AI)
    decisions = []
    discoveries = []
    changes = []
    next_actions = []
    
    for msg in session_data.get('messages', []):
        content = msg.get('content', '').lower()
        
        # Look for decision patterns
        if any(word in content for word in ['decided', 'chose', 'configured', 'set']):
            decisions.append(msg.get('content', '')[:200])
        
        # Look for discovery patterns  
        if any(word in content for word in ['found', 'discovered', 'learned', 'realized']):
            discoveries.append(msg.get('content', '')[:200])
            
        # Look for file changes
        if any(word in content for word in ['edited', 'updated', 'modified', 'created']):
            changes.append(msg.get('content', '')[:200])
            
        # Look for action items
        if any(word in content for word in ['todo', 'need to', 'should', 'will', 'next']):
            next_actions.append(msg.get('content', '')[:200])
    
    return {
        'decisions': decisions[:5],  # Limit to top 5
        'discoveries': discoveries[:5],
        'changes': changes[:5],
        'next_actions': next_actions[:3]
    }

def create_session_summary(session_id, token_count, session_data):
    """Create structured summary for Obsidian-Memory vault"""
    timestamp = datetime.now()
    key_points = extract_key_points(session_data)
    
    summary = f"""# Session Summary {timestamp.strftime('%Y-%m-%d %H:%M')}

## Context
- **Session:** {session_id}
- **Timestamp:** {timestamp.isoformat()}
- **Token count:** {token_count:,}
- **Status:** Auto-summarized before reset

## Key Decisions
"""
    
    for decision in key_points['decisions']:
        summary += f"- {decision}\n"
    
    summary += "\n## Important Discoveries\n"
    for discovery in key_points['discoveries']:
        summary += f"- {discovery}\n"
        
    summary += "\n## Changes Made\n"
    for change in key_points['changes']:
        summary += f"- {change}\n"
        
    summary += "\n## Next Actions\n"
    for action in key_points['next_actions']:
        summary += f"- {action}\n"
        
    summary += f"\n## Meta\n- Summarized via token-monitor integration\n- Original session archived\n"
    
    return summary

def store_summary(summary, session_id):
    """Store summary in Obsidian-Memory vault"""
    timestamp = datetime.now()
    vault_path = Path.home() / "Obsidian-Memory" / "brain" / "memory" / "session-summaries"
    vault_path.mkdir(parents=True, exist_ok=True)
    
    filename = f"{timestamp.strftime('%Y-%m-%d-%H%M')}-session-{session_id[:8]}.md"
    filepath = vault_path / filename
    
    with open(filepath, 'w') as f:
        f.write(summary)
    
    print(f"Session summary saved: {filepath}")
    return filepath

def main():
    parser = argparse.ArgumentParser(description='Auto-summarize session before reset')
    parser.add_argument('--session-id', required=True, help='Session ID to summarize')
    parser.add_argument('--token-count', type=int, required=True, help='Current token count')
    parser.add_argument('--dry-run', action='store_true', help='Show summary without saving')
    
    args = parser.parse_args()
    
    print(f"Summarizing session {args.session_id} ({args.token_count:,} tokens)")
    
    # Get session data
    session_data = get_session_context(args.session_id)
    if not session_data:
        print("No session data available for summarization")
        return 1
    
    # Create summary
    summary = create_session_summary(args.session_id, args.token_count, session_data)
    
    if args.dry_run:
        print("DRY RUN - Summary would be:")
        print(summary)
        return 0
    
    # Store in vault
    try:
        filepath = store_summary(summary, args.session_id)
        print(f"✅ Session context preserved in Memory vault")
        
        # Update today's memory log
        today_file = Path.home() / "Obsidian-Memory" / "brain" / "memory" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
        if today_file.exists():
            with open(today_file, 'a') as f:
                f.write(f"\n## Session Reset - {datetime.now().strftime('%H:%M')}\n")
                f.write(f"- **Session:** {args.session_id}\n")
                f.write(f"- **Tokens:** {args.token_count:,}\n")
                f.write(f"- **Summary:** [[{filepath.stem}]]\n")
                f.write(f"- **Action:** Auto-reset to prevent bloat\n")
        
        return 0
    except Exception as e:
        print(f"Failed to store summary: {e}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())