"""Knowledge consolidation service - enhances existing notes instead of creating new files."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.note import NoteType, RelationType
from app.models.session import Session, SessionEventType
from app.services.ai_processor import AIProcessor
from app.services.vault_manager import VaultManager

logger = logging.getLogger(__name__)


class KnowledgeConsolidator:
    """Service for consolidating session knowledge into existing note structure."""

    def __init__(self, vault_manager: VaultManager, ai_processor: AIProcessor):
        self.vault_manager = vault_manager
        self.ai_processor = ai_processor

    async def consolidate_session(self, session: Session) -> dict[str, Any]:
        """Consolidate session knowledge into existing notes.
        
        Instead of creating new files, this:
        1. Extracts knowledge from session events
        2. Updates existing knowledge/decision notes
        3. Creates cross-references and relationships
        4. Archives session summary
        
        Returns summary of consolidation actions taken.
        """
        if not session.events:
            return {"status": "no_events", "actions": []}

        # Generate AI summary first
        session_text = self._format_session_for_ai(session)
        summary = await self.ai_processor.summarize_session(session_text)
        
        actions = []
        
        # Process decisions -> update/create decision notes
        for decision in summary.decisions:
            action = await self._consolidate_decision(decision, session.session_id)
            if action:
                actions.append(action)
        
        # Process key learnings -> update knowledge notes
        for learning in summary.key_learnings:
            action = await self._consolidate_learning(learning, session.session_id)
            if action:
                actions.append(action)
                
        # Process errors/solutions -> update error/solution notes
        for error, solution in zip(summary.errors_encountered, summary.solutions_found):
            action = await self._consolidate_error_solution(error, solution, session.session_id)
            if action:
                actions.append(action)
        
        # Create session archive note
        archive_action = await self._create_session_archive(session, summary)
        if archive_action:
            actions.append(archive_action)
            
        return {
            "status": "consolidated",
            "session_id": session.session_id,
            "actions": actions,
            "summary": summary.summary_text
        }

    async def _consolidate_decision(self, decision: str, session_id: str) -> dict[str, Any] | None:
        """Update existing decision note or create new one."""
        
        # Extract topic from decision
        topic = await self._extract_topic_from_decision(decision)
        if not topic:
            return None
            
        # Look for existing decision note with similar topic
        existing_note_path = await self._find_existing_note(topic, NoteType.DECISION)
        
        if existing_note_path:
            # Update existing note
            return await self._update_decision_note(existing_note_path, decision, session_id)
        else:
            # Create new decision note
            return await self._create_decision_note(topic, decision, session_id)

    async def _consolidate_learning(self, learning: str, session_id: str) -> dict[str, Any] | None:
        """Update existing knowledge note or create new one."""
        
        # Extract topic from learning
        topic = await self._extract_topic_from_learning(learning)
        if not topic:
            return None
            
        # Look for existing knowledge note
        existing_note_path = await self._find_existing_note(topic, NoteType.KNOWLEDGE)
        
        if existing_note_path:
            # Update existing note
            return await self._update_knowledge_note(existing_note_path, learning, session_id)
        else:
            # Create new knowledge note
            return await self._create_knowledge_note(topic, learning, session_id)

    async def _extract_topic_from_decision(self, decision: str) -> str | None:
        """Use AI to extract topic/theme from decision text."""
        if not self.ai_processor.enabled:
            # Fallback: simple keyword extraction
            keywords = ["token", "model", "session", "config", "workspace", "memory"]
            for keyword in keywords:
                if keyword in decision.lower():
                    return keyword
            return "general"
            
        system_prompt = """Extract a single topic slug from this decision text.
Return just the topic slug (lowercase, hyphenated, no spaces).
Examples: "token-efficiency", "workspace-setup", "model-config"
"""
        
        try:
            response = await self.ai_processor._call_claude(
                system_prompt=system_prompt,
                user_prompt=f"Decision: {decision}",
                max_tokens=50
            )
            return response.strip().lower().replace(" ", "-")
        except Exception as e:
            logger.warning(f"Failed to extract topic from decision: {e}")
            return "general"

    async def _extract_topic_from_learning(self, learning: str) -> str | None:
        """Use AI to extract topic/theme from learning text."""
        # Similar to _extract_topic_from_decision but for learnings
        return await self._extract_topic_from_decision(learning)  # Reuse logic

    async def _find_existing_note(self, topic: str, note_type: NoteType) -> Path | None:
        """Find existing note with similar topic and type."""
        # Search for notes with matching topic in title or permalink
        notes = await self.vault_manager.list_notes()
        
        for note_path in notes:
            try:
                parsed = await self.vault_manager.parse_note(note_path)
                
                # Check if note type matches
                if parsed.frontmatter.type != note_type:
                    continue
                    
                # Check if topic appears in title or permalink
                title_lower = parsed.frontmatter.title.lower()
                permalink_lower = (parsed.frontmatter.permalink or "").lower()
                
                if topic in title_lower or topic in permalink_lower:
                    return note_path
                    
            except Exception as e:
                logger.warning(f"Error checking note {note_path}: {e}")
                continue
                
        return None

    async def _update_decision_note(self, note_path: Path, decision: str, session_id: str) -> dict[str, Any]:
        """Update existing decision note with new decision."""
        try:
            # Read existing note
            parsed = await self.vault_manager.parse_note(note_path)
            
            # Add new decision to content
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_content = f"\n\n## Decision - {timestamp}\n{decision}\n\n*Source: [[session-{session_id}]]*"
            
            # Update content
            updated_content = parsed.raw_content + new_content
            
            # Update frontmatter
            updated_frontmatter = parsed.frontmatter.model_copy()
            updated_frontmatter.updated = datetime.now()
            
            # Write updated note
            await self.vault_manager.write_note(
                path=note_path,
                frontmatter=updated_frontmatter.model_dump(exclude_unset=True),
                content=updated_content
            )
            
            return {
                "action": "updated_decision",
                "note_path": str(note_path),
                "decision": decision[:100] + "..." if len(decision) > 100 else decision
            }
            
        except Exception as e:
            logger.error(f"Failed to update decision note {note_path}: {e}")
            return None

    async def _update_knowledge_note(self, note_path: Path, learning: str, session_id: str) -> dict[str, Any]:
        """Update existing knowledge note with new learning."""
        # Similar logic to _update_decision_note
        try:
            parsed = await self.vault_manager.parse_note(note_path)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_content = f"\n\n## Learning - {timestamp}\n{learning}\n\n*Source: [[session-{session_id}]]*"
            
            updated_content = parsed.raw_content + new_content
            
            updated_frontmatter = parsed.frontmatter.model_copy()
            updated_frontmatter.updated = datetime.now()
            
            await self.vault_manager.write_note(
                path=note_path,
                frontmatter=updated_frontmatter.model_dump(exclude_unset=True),
                content=updated_content
            )
            
            return {
                "action": "updated_knowledge",
                "note_path": str(note_path),
                "learning": learning[:100] + "..." if len(learning) > 100 else learning
            }
            
        except Exception as e:
            logger.error(f"Failed to update knowledge note {note_path}: {e}")
            return None

    async def _create_decision_note(self, topic: str, decision: str, session_id: str) -> dict[str, Any]:
        """Create new decision note."""
        try:
            timestamp = datetime.now()
            
            frontmatter = {
                "title": f"{topic.replace('-', ' ').title()} Decisions",
                "type": "decision",
                "permalink": f"{topic}-decisions",
                "created": timestamp.isoformat(),
                "updated": timestamp.isoformat(),
                "tags": [topic]
            }
            
            content = f"""# {frontmatter['title']}

## Decision - {timestamp.strftime("%Y-%m-%d %H:%M")}
{decision}

*Source: [[session-{session_id}]]*

## Related
- Add links to related notes here
"""
            
            note_path = Path(f"decisions/{topic}-decisions.md")
            await self.vault_manager.write_note(
                path=note_path,
                frontmatter=frontmatter,
                content=content
            )
            
            return {
                "action": "created_decision",
                "note_path": str(note_path),
                "topic": topic,
                "decision": decision[:100] + "..." if len(decision) > 100 else decision
            }
            
        except Exception as e:
            logger.error(f"Failed to create decision note for topic {topic}: {e}")
            return None

    async def _create_knowledge_note(self, topic: str, learning: str, session_id: str) -> dict[str, Any]:
        """Create new knowledge note."""
        # Similar logic to _create_decision_note
        try:
            timestamp = datetime.now()
            
            frontmatter = {
                "title": f"{topic.replace('-', ' ').title()} Knowledge",
                "type": "knowledge", 
                "permalink": f"{topic}-knowledge",
                "created": timestamp.isoformat(),
                "updated": timestamp.isoformat(),
                "tags": [topic]
            }
            
            content = f"""# {frontmatter['title']}

## Learning - {timestamp.strftime("%Y-%m-%d %H:%M")}
{learning}

*Source: [[session-{session_id}]]*

## Related
- Add links to related notes here
"""
            
            note_path = Path(f"knowledge/{topic}-knowledge.md")
            await self.vault_manager.write_note(
                path=note_path,
                frontmatter=frontmatter,
                content=content
            )
            
            return {
                "action": "created_knowledge",
                "note_path": str(note_path),
                "topic": topic,
                "learning": learning[:100] + "..." if len(learning) > 100 else learning
            }
            
        except Exception as e:
            logger.error(f"Failed to create knowledge note for topic {topic}: {e}")
            return None

    async def _consolidate_error_solution(self, error: str, solution: str, session_id: str) -> dict[str, Any] | None:
        """Create or update error/solution notes."""
        # Similar pattern but for errors and solutions
        # Could create combined error-solution notes or separate ones
        return None  # Implement as needed

    async def _create_session_archive(self, session: Session, summary) -> dict[str, Any]:
        """Create archived session summary for reference."""
        try:
            timestamp = session.started_at or datetime.now()
            
            frontmatter = {
                "title": f"Session {timestamp.strftime('%Y-%m-%d %H:%M')}",
                "type": "session",
                "permalink": f"session-{session.session_id}",
                "created": timestamp.isoformat(),
                "tags": ["session", "archive"]
            }
            
            content = f"""# {frontmatter['title']}

## Summary
{summary.summary_text}

## Key Outcomes
### Decisions Made
{chr(10).join(f"- {d}" for d in summary.decisions)}

### Key Learnings
{chr(10).join(f"- {l}" for l in summary.key_learnings)}

### Next Steps
{chr(10).join(f"- {n}" for n in summary.next_steps)}

## Metadata
- **Session ID:** {session.session_id}
- **Project:** {session.project or "None"}
- **Duration:** {self._calculate_duration(session)}
- **Events:** {len(session.events)}
"""
            
            note_path = Path(f"sessions/archive/session-{session.session_id[:8]}.md")
            await self.vault_manager.write_note(
                path=note_path,
                frontmatter=frontmatter,
                content=content
            )
            
            return {
                "action": "archived_session",
                "note_path": str(note_path),
                "session_id": session.session_id
            }
            
        except Exception as e:
            logger.error(f"Failed to archive session {session.session_id}: {e}")
            return None

    def _format_session_for_ai(self, session: Session) -> str:
        """Format session events for AI processing."""
        events_text = []
        
        for event in session.events:
            event_text = f"[{event.timestamp.strftime('%H:%M')}] {event.event_type}: {event.content}"
            events_text.append(event_text)
            
        return "\n".join(events_text)

    def _calculate_duration(self, session: Session) -> str:
        """Calculate session duration."""
        if not session.started_at or not session.ended_at:
            return "Unknown"
            
        duration = session.ended_at - session.started_at
        hours = duration.total_seconds() / 3600
        
        if hours < 1:
            minutes = int(duration.total_seconds() / 60)
            return f"{minutes} minutes"
        else:
            return f"{hours:.1f} hours"