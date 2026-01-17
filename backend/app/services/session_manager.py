"""Session management service."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from app.config import settings
from app.models.session import (
    Session,
    SessionEvent,
    SessionEventType,
)
from app.services.ai_processor import AIProcessor
from app.services.exceptions import AIProcessorUnavailableError


class SessionManager:
    """Manages session tracking and storage."""

    def __init__(self, storage_path: Path | None = None) -> None:
        """Initialize session manager.

        Args:
            storage_path: Path to store session files (defaults to ~/.obsidian-memory/sessions)
        """
        if storage_path is None:
            storage_path = Path.home() / ".obsidian-memory" / "sessions"
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, Session] = {}

    def _get_session_file(self, session_id: str) -> Path:
        """Get path to session file."""
        return self.storage_path / f"{session_id}.json"

    async def create_session(
        self, project: str | None = None, session_id: str | None = None
    ) -> Session:
        """Create a new session.

        Args:
            project: Optional project name
            session_id: Optional custom session ID (defaults to UUID)

        Returns:
            Created session
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        session = Session(
            session_id=session_id,
            project=project,
            started_at=datetime.now(),
            status="active",
        )

        self._sessions[session_id] = session
        await self._save_session(session)

        return session

    async def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session if found, None otherwise
        """
        # Check in-memory cache first
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Try to load from disk
        session_file = self._get_session_file(session_id)
        if session_file.exists():
            try:
                async with aiofiles.open(session_file, "r", encoding="utf-8") as f:
                    data = json.loads(await f.read())
                    session = Session(**data)
                    self._sessions[session_id] = session
                    return session
            except Exception:
                return None

        return None

    async def observe_event(
        self,
        session_id: str,
        event_type: SessionEventType,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Add an observation/event to a session.

        Args:
            session_id: Session identifier
            event_type: Type of event
            content: Event content
            metadata: Optional metadata

        Returns:
            Updated session

        Raises:
            ValueError: If session not found
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        event = SessionEvent(
            event_type=event_type,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )

        session.events.append(event)
        self._sessions[session_id] = session
        await self._save_session(session)

        return session

    async def end_session(self, session_id: str) -> Session:
        """End a session.

        Args:
            session_id: Session identifier

        Returns:
            Updated session

        Raises:
            ValueError: If session not found
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.ended_at = datetime.now()
        session.status = "completed"
        self._sessions[session_id] = session
        await self._save_session(session)

        return session

    async def summarize_session(
        self, session_id: str, ai_processor: AIProcessor | None = None
    ) -> dict[str, Any]:
        """Generate AI summary for a session.

        Args:
            session_id: Session identifier
            ai_processor: Optional AI processor (creates one if not provided)

        Returns:
            Session summary dictionary
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Build session content from events
        event_lines = []
        for event in session.events:
            event_lines.append(
                f"[{event.event_type.value}] {event.timestamp.isoformat()}: {event.content}"
            )
        session_content = "\n".join(event_lines)

        # Use AI processor to summarize
        if ai_processor is None:
            ai_processor = AIProcessor()

        try:
            summary = await ai_processor.summarize_session(session_content)
            session.summary = summary.model_dump()
            await self._save_session(session)
            return session.summary
        except AIProcessorUnavailableError:
            # Return basic summary if AI unavailable
            return {
                "key_learnings": [],
                "decisions": [],
                "errors_encountered": [],
                "solutions_found": [],
                "next_steps": [],
                "summary_text": f"Session with {len(session.events)} events",
                "compression_ratio": 0.0,
            }

    async def get_session_context(
        self,
        session_id: str,
        include_events: bool = True,
        include_summary: bool = True,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get context for a session.

        Args:
            session_id: Session identifier
            include_events: Whether to include events
            include_summary: Whether to include summary
            limit: Maximum number of events to return

        Returns:
            Session context dictionary
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        context: dict[str, Any] = {
            "session_id": session.session_id,
            "project": session.project,
            "started_at": session.started_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "status": session.status,
            "event_count": len(session.events),
        }

        if include_events:
            events = session.events[-limit:] if limit > 0 else session.events
            context["events"] = [
                {
                    "event_type": e.event_type.value,
                    "content": e.content,
                    "timestamp": e.timestamp.isoformat(),
                    "metadata": e.metadata,
                }
                for e in events
            ]

        if include_summary and session.summary:
            context["summary"] = session.summary

        return context

    async def _save_session(self, session: Session) -> None:
        """Save session to disk."""
        session_file = self._get_session_file(session.session_id)
        async with aiofiles.open(session_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(session.model_dump(), default=str, indent=2))

    async def list_sessions(
        self, project: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List sessions.

        Args:
            project: Optional project filter
            limit: Maximum number of sessions to return

        Returns:
            List of session summaries
        """
        sessions = []

        # Load all session files
        for session_file in self.storage_path.glob("*.json"):
            try:
                async with aiofiles.open(session_file, "r", encoding="utf-8") as f:
                    data = json.loads(await f.read())
                    session = Session(**data)

                    if project is None or session.project == project:
                        sessions.append(
                            {
                                "session_id": session.session_id,
                                "project": session.project,
                                "started_at": session.started_at.isoformat(),
                                "ended_at": session.ended_at.isoformat()
                                if session.ended_at
                                else None,
                                "status": session.status,
                                "event_count": len(session.events),
                            }
                        )
            except Exception:
                continue

        # Sort by started_at descending
        sessions.sort(key=lambda x: x["started_at"], reverse=True)

        return sessions[:limit]
