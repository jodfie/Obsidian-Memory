"""Session management service."""

import hashlib
import json
import logging
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

logger = logging.getLogger(__name__)


def generate_custom_id(
    session_id: str, event_type: SessionEventType, content: str
) -> str:
    """Generate deterministic custom_id for session event deduplication.

    Format: session_{session_id}_{event_type}_{content_hash[:8]}

    Same inputs always produce the same ID, enabling callers to
    detect and update duplicate events automatically.
    """
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
    return f"session_{session_id}_{event_type.value}_{content_hash}"


# Configuration for incremental summarization
DEFAULT_CHUNK_SIZE = 50  # Events per chunk
AUTO_SUMMARIZE_THRESHOLD = 100  # Auto-summarize every N events
SESSION_END_SUMMARIZE_THRESHOLD = 10  # Minimum events to trigger end-of-session summary


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
        custom_id: str | None = None,
    ) -> Session:
        """Add an observation/event to a session (with optional upsert).

        When custom_id is provided, an existing event with the same
        custom_id is updated instead of appending a duplicate.
        When custom_id is None, behavior is append-only (backward compatible).

        Args:
            session_id: Session identifier
            event_type: Type of event
            content: Event content
            metadata: Optional metadata
            custom_id: Optional deduplication key (enables upsert)

        Returns:
            Updated session

        Raises:
            ValueError: If session not found
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if custom_id is not None:
            # Upsert: find existing event with matching custom_id
            existing_idx = next(
                (
                    i
                    for i, e in enumerate(session.events)
                    if getattr(e, "custom_id", None) == custom_id
                ),
                None,
            )
            if existing_idx is not None:
                # Update existing event in place
                existing = session.events[existing_idx]
                existing.content = content
                existing.event_type = event_type
                existing.metadata = metadata or {}
                existing.updated_at = datetime.now()
            else:
                # Insert new event with custom_id
                event = SessionEvent(
                    event_type=event_type,
                    content=content,
                    timestamp=datetime.now(),
                    metadata=metadata or {},
                    custom_id=custom_id,
                )
                session.events.append(event)
        else:
            # Original append-only behavior (backward compatible)
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

    async def end_session(
        self,
        session_id: str,
        auto_summarize: bool = True,
        ai_processor: AIProcessor | None = None,
    ) -> Session:
        """End a session.

        Args:
            session_id: Session identifier
            auto_summarize: If True, automatically summarize if threshold met
            ai_processor: Optional AI processor for summarization

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

        # Auto-summarize on session end if enabled and threshold met
        if auto_summarize and len(session.events) >= SESSION_END_SUMMARIZE_THRESHOLD:
            try:
                logger.info(
                    f"Auto-summarizing session {session_id} on end "
                    f"({len(session.events)} events)"
                )
                await self.summarize_session(session_id, ai_processor)
                # Reload session to get updated summary
                session = await self.get_session(session_id)
            except Exception as e:
                logger.warning(f"Failed to auto-summarize session on end: {e}")

        await self._save_session(session)

        return session

    async def summarize_session(
        self,
        session_id: str,
        ai_processor: AIProcessor | None = None,
        force_incremental: bool = False,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> dict[str, Any]:
        """Generate AI summary for a session.

        Supports incremental summarization for long sessions by chunking events
        and creating a meta-summary.

        Args:
            session_id: Session identifier
            ai_processor: Optional AI processor (creates one if not provided)
            force_incremental: Force incremental summarization regardless of size
            chunk_size: Number of events per chunk for incremental summarization

        Returns:
            Session summary dictionary
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Use AI processor to summarize
        if ai_processor is None:
            ai_processor = AIProcessor()

        # Determine if we should use incremental summarization
        use_incremental = force_incremental or len(session.events) > chunk_size * 2

        try:
            if use_incremental and len(session.events) > chunk_size:
                summary = await self._summarize_incremental(
                    session, ai_processor, chunk_size
                )
            else:
                # Build session content from events
                session_content = self._format_events(session.events)
                summary = await ai_processor.summarize_session(session_content)

            session.summary = summary.model_dump()
            # Track summarization metadata
            if session.metadata is None:
                session.metadata = {}
            session.metadata["last_summarized_at"] = datetime.now().isoformat()
            session.metadata["summarized_event_count"] = len(session.events)

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
                "topics": [],
                "participants": [],
                "actionable_items": [],
                "related_notes": [],
                "summary_text": f"Session with {len(session.events)} events",
                "compression_ratio": 0.0,
                "chunk_count": 1,
                "is_incremental": False,
            }

    async def _summarize_incremental(
        self,
        session: Session,
        ai_processor: AIProcessor,
        chunk_size: int,
    ) -> "SessionSummary":
        """Perform incremental summarization by chunking events.

        Args:
            session: Session to summarize
            ai_processor: AI processor instance
            chunk_size: Number of events per chunk

        Returns:
            SessionSummary from incremental processing
        """
        from app.models.ai import SessionSummary

        # Chunk events
        event_chunks = []
        for i in range(0, len(session.events), chunk_size):
            chunk_events = session.events[i : i + chunk_size]
            chunk_content = self._format_events(chunk_events)
            event_chunks.append(chunk_content)

        logger.info(
            f"Incrementally summarizing session {session.session_id} "
            f"with {len(event_chunks)} chunks"
        )

        # Use incremental summarization
        return await ai_processor.summarize_session_incremental(event_chunks)

    def _format_events(self, events: list[SessionEvent]) -> str:
        """Format events into a string for summarization.

        Args:
            events: List of session events

        Returns:
            Formatted string of events
        """
        event_lines = []
        for event in events:
            event_lines.append(
                f"[{event.event_type.value}] {event.timestamp.isoformat()}: {event.content}"
            )
        return "\n".join(event_lines)

    async def should_auto_summarize(self, session_id: str) -> bool:
        """Check if a session should be auto-summarized.

        Auto-summarization is triggered when:
        - Session has more than AUTO_SUMMARIZE_THRESHOLD events since last summary
        - Session has never been summarized and has enough events

        Args:
            session_id: Session identifier

        Returns:
            True if auto-summarization should be triggered
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        # Get last summarized event count
        last_summarized_count = 0
        if session.metadata:
            last_summarized_count = session.metadata.get("summarized_event_count", 0)

        events_since_summary = len(session.events) - last_summarized_count
        return events_since_summary >= AUTO_SUMMARIZE_THRESHOLD

    async def auto_summarize_if_needed(
        self,
        session_id: str,
        ai_processor: AIProcessor | None = None,
    ) -> dict[str, Any] | None:
        """Auto-summarize session if threshold is reached.

        Args:
            session_id: Session identifier
            ai_processor: Optional AI processor

        Returns:
            Session summary if summarization was triggered, None otherwise
        """
        if await self.should_auto_summarize(session_id):
            logger.info(f"Auto-summarizing session {session_id}")
            return await self.summarize_session(session_id, ai_processor)
        return None

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
