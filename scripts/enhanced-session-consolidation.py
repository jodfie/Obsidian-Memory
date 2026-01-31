#!/usr/bin/env python3
"""
Enhanced Session Consolidation Script

Integrates with Clawdbot token monitoring to:
1. Trigger consolidation when sessions approach token limits
2. Use existing Obsidian-Memory AI processor for smart summarization
3. Update existing knowledge notes instead of creating new files
4. Archive session summaries with cross-references

Usage:
  python3 enhanced-session-consolidation.py --session-id <id> --token-count <count>
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import argparse
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClawdbotSessionConsolidator:
    """Consolidates Clawdbot sessions using Obsidian-Memory architecture."""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url.rstrip("/")
        
    async def consolidate_session(self, session_id: str, token_count: int) -> dict[str, Any]:
        """Consolidate a high-token session into knowledge base."""
        
        # Get session data from Clawdbot
        session_data = await self._get_clawdbot_session(session_id)
        if not session_data:
            return {"status": "error", "message": "Could not retrieve session data"}
        
        # Convert Clawdbot session to Obsidian-Memory session format
        memory_session = await self._convert_session_format(session_data, session_id, token_count)
        
        # Use Obsidian-Memory API for consolidation
        consolidation_result = await self._call_memory_consolidation(memory_session)
        
        # Log consolidation to today's memory file
        await self._log_consolidation(session_id, token_count, consolidation_result)
        
        return consolidation_result

    async def _get_clawdbot_session(self, session_id: str) -> dict | None:
        """Get session data from Clawdbot API."""
        try:
            import subprocess
            import json
            
            # Use clawdbot CLI to get session history
            result = subprocess.run([
                'clawdbot', 'sessions', 'history',
                '--session-key', session_id,
                '--limit', '100',
                '--format', 'json'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"Failed to get session history: {result.stderr}")
                return None
                
            return json.loads(result.stdout)
            
        except Exception as e:
            logger.error(f"Error getting session data: {e}")
            return None

    async def _convert_session_format(self, clawdbot_session: dict, session_id: str, token_count: int) -> dict:
        """Convert Clawdbot session format to Obsidian-Memory session format."""
        
        events = []
        messages = clawdbot_session.get('messages', [])
        
        for msg in messages:
            # Convert message to session event
            content = msg.get('content', '')
            timestamp = msg.get('timestamp', datetime.now().isoformat())
            role = msg.get('role', 'user')
            
            # Classify event type based on content
            event_type = self._classify_event_type(content, role)
            
            events.append({
                "event_type": event_type,
                "content": content[:1000],  # Limit content length
                "timestamp": timestamp,
                "metadata": {
                    "role": role,
                    "original_length": len(content),
                    "token_count": token_count
                }
            })
        
        return {
            "session_id": session_id,
            "project": None,  # Could extract from session context
            "started_at": messages[0].get('timestamp') if messages else datetime.now().isoformat(),
            "ended_at": datetime.now().isoformat(),
            "events": events,
            "status": "completed"
        }

    def _classify_event_type(self, content: str, role: str) -> str:
        """Classify message content into event types."""
        content_lower = content.lower()
        
        if role == 'user':
            return "user_prompt"
        
        # Look for tool usage
        if any(word in content_lower for word in ['exec', 'read', 'write', 'edit', 'bash']):
            return "tool_use"
        
        # Look for file operations
        if any(word in content_lower for word in ['created', 'updated', 'modified', 'file']):
            return "file_edit"
        
        # Look for decisions
        if any(word in content_lower for word in ['decided', 'configured', 'set', 'changed']):
            return "decision"
        
        # Look for errors
        if any(word in content_lower for word in ['error', 'failed', 'exception']):
            return "error"
        
        # Look for solutions
        if any(word in content_lower for word in ['solved', 'fixed', 'resolved', 'solution']):
            return "solution"
        
        # Default to observation
        return "observation"

    async def _call_memory_consolidation(self, session: dict) -> dict[str, Any]:
        """Call Obsidian-Memory consolidation API."""
        try:
            async with aiohttp.ClientSession() as client:
                # Check if Obsidian-Memory backend is running
                try:
                    async with client.get(f"{self.api_url}/health") as response:
                        if response.status != 200:
                            return await self._fallback_consolidation(session)
                except:
                    return await self._fallback_consolidation(session)
                
                # Call consolidation endpoint (would need to be added to backend)
                async with client.post(
                    f"{self.api_url}/api/sessions/consolidate",
                    json=session
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"Consolidation API returned {response.status}")
                        return await self._fallback_consolidation(session)
                        
        except Exception as e:
            logger.error(f"Error calling consolidation API: {e}")
            return await self._fallback_consolidation(session)

    async def _fallback_consolidation(self, session: dict) -> dict[str, Any]:
        """Fallback consolidation when Obsidian-Memory API unavailable."""
        logger.info("Using fallback consolidation")
        
        # Extract key information manually
        decisions = []
        learnings = []
        errors = []
        
        for event in session.get('events', []):
            content = event.get('content', '')
            event_type = event.get('event_type', '')
            
            if event_type == 'decision':
                decisions.append(content[:200])
            elif event_type in ['observation', 'solution']:
                learnings.append(content[:200])
            elif event_type == 'error':
                errors.append(content[:200])
        
        # Create simple summary file
        summary_file = await self._create_fallback_summary(session, decisions, learnings, errors)
        
        return {
            "status": "fallback_consolidation",
            "session_id": session['session_id'],
            "actions": [
                {
                    "action": "created_summary",
                    "note_path": summary_file,
                    "decisions_count": len(decisions),
                    "learnings_count": len(learnings),
                    "errors_count": len(errors)
                }
            ]
        }

    async def _create_fallback_summary(self, session: dict, decisions: list, learnings: list, errors: list) -> str:
        """Create simple summary file when full consolidation unavailable."""
        
        timestamp = datetime.now()
        session_id = session['session_id']
        
        # Use brain workspace directory
        brain_dir = Path.home() / "Obsidian-Memory" / "brain"
        summaries_dir = brain_dir / "memory" / "session-summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{timestamp.strftime('%Y-%m-%d-%H%M')}-session-{session_id[:8]}.md"
        filepath = summaries_dir / filename
        
        content = f"""# Session Summary {timestamp.strftime('%Y-%m-%d %H:%M')}

## Context
- **Session ID:** {session_id}
- **Timestamp:** {timestamp.isoformat()}
- **Events:** {len(session.get('events', []))}
- **Status:** Fallback consolidation (Obsidian-Memory API unavailable)

## Key Decisions ({len(decisions)})
"""
        
        for decision in decisions:
            content += f"- {decision}\n"
            
        content += f"\n## Key Learnings ({len(learnings)})\n"
        for learning in learnings:
            content += f"- {learning}\n"
            
        content += f"\n## Errors Encountered ({len(errors)})\n"
        for error in errors:
            content += f"- {error}\n"
            
        content += f"""
## Next Steps
- Review and integrate key decisions into permanent knowledge notes
- Cross-reference related topics
- Archive this session summary

## Meta
- Consolidation method: Fallback (simple extraction)
- Original session archived
- Requires manual review and integration
"""

        with open(filepath, 'w') as f:
            f.write(content)
            
        return str(filepath)

    async def _log_consolidation(self, session_id: str, token_count: int, result: dict):
        """Log consolidation to today's memory file."""
        try:
            brain_dir = Path.home() / "Obsidian-Memory" / "brain"
            memory_dir = brain_dir / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            
            today_file = memory_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
            
            log_entry = f"""
## Session Consolidation - {datetime.now().strftime('%H:%M')}

- **Session ID:** {session_id}
- **Token Count:** {token_count:,}
- **Status:** {result.get('status', 'unknown')}
- **Actions Taken:** {len(result.get('actions', []))}

### Actions
"""
            
            for action in result.get('actions', []):
                action_type = action.get('action', 'unknown')
                note_path = action.get('note_path', 'N/A')
                log_entry += f"- **{action_type}**: {note_path}\n"
            
            log_entry += "\n### Summary\n"
            summary_text = result.get('summary', 'No summary available')
            log_entry += f"{summary_text[:300]}{'...' if len(summary_text) > 300 else ''}\n"
            
            # Append to today's file
            if today_file.exists():
                with open(today_file, 'a') as f:
                    f.write(log_entry)
            else:
                # Create today's file if it doesn't exist
                header = f"# {datetime.now().strftime('%Y-%m-%d')} - Session Consolidations\n"
                with open(today_file, 'w') as f:
                    f.write(header + log_entry)
                    
        except Exception as e:
            logger.error(f"Failed to log consolidation: {e}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Consolidate Clawdbot session into knowledge base')
    parser.add_argument('--session-id', required=True, help='Session ID to consolidate')
    parser.add_argument('--token-count', type=int, required=True, help='Current token count')
    parser.add_argument('--api-url', default='http://localhost:8000', help='Obsidian-Memory API URL')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    
    args = parser.parse_args()
    
    consolidator = ClawdbotSessionConsolidator(api_url=args.api_url)
    
    logger.info(f"Starting consolidation for session {args.session_id} ({args.token_count:,} tokens)")
    
    if args.dry_run:
        logger.info("DRY RUN: Would consolidate session knowledge")
        return 0
    
    try:
        result = await consolidator.consolidate_session(args.session_id, args.token_count)
        
        if result.get('status') == 'error':
            logger.error(f"Consolidation failed: {result.get('message')}")
            return 1
            
        logger.info("✅ Session consolidation completed")
        logger.info(f"Status: {result.get('status')}")
        logger.info(f"Actions taken: {len(result.get('actions', []))}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Consolidation failed with exception: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))