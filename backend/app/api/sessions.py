"""Session management API endpoints."""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.models.session import (
    SessionContextRequest,
    SessionEventType,
    SessionObserveRequest,
)
from app.services.ai_processor import AIProcessor
from app.services.session_manager import SessionManager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def get_session_manager() -> SessionManager:
    """Get session manager instance."""
    return SessionManager()


@router.post("")
async def create_session(
    project: str | None = Body(None, embed=True),
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Create a new session.

    Args:
        project: Optional project name
        session_manager: Session manager dependency

    Returns:
        Created session information
    """
    session = await session_manager.create_session(project=project)
    return {
        "session_id": session.session_id,
        "project": session.project,
        "started_at": session.started_at.isoformat(),
        "status": session.status,
    }


@router.post("/observe")
async def observe_event(
    request: SessionObserveRequest,
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Add an observation/event to a session.

    Args:
        request: Observation request
        session_manager: Session manager dependency

    Returns:
        Updated session information
    """
    try:
        session = await session_manager.observe_event(
            session_id=request.session_id,
            event_type=request.event_type,
            content=request.content,
            metadata=request.metadata,
        )
        return {
            "session_id": session.session_id,
            "event_count": len(session.events),
            "status": session.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{session_id}/summary")
async def summarize_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
    ai_processor: AIProcessor | None = Depends(lambda: AIProcessor()),
) -> dict[str, Any]:
    """Generate AI summary for a session.

    Args:
        session_id: Session identifier
        session_manager: Session manager dependency
        ai_processor: AI processor dependency

    Returns:
        Session summary
    """
    try:
        summary = await session_manager.summarize_session(
            session_id=session_id, ai_processor=ai_processor
        )
        return summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/context")
async def get_session_context(
    request: SessionContextRequest,
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Get context for a session.

    Args:
        request: Context request
        session_manager: Session manager dependency

    Returns:
        Session context
    """
    try:
        context = await session_manager.get_session_context(
            session_id=request.session_id,
            include_events=request.include_events,
            include_summary=request.include_summary,
            limit=request.limit,
        )
        return context
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Get a session by ID.

    Args:
        session_id: Session identifier
        session_manager: Session manager dependency

    Returns:
        Session information
    """
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return {
        "session_id": session.session_id,
        "project": session.project,
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "status": session.status,
        "event_count": len(session.events),
    }


@router.post("/{session_id}/end")
async def end_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """End a session.

    Args:
        session_id: Session identifier
        session_manager: Session manager dependency

    Returns:
        Updated session information
    """
    try:
        session = await session_manager.end_session(session_id)
        return {
            "session_id": session.session_id,
            "status": session.status,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("")
async def list_sessions(
    project: str | None = None,
    limit: int = 50,
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """List sessions.

    Args:
        project: Optional project filter
        limit: Maximum number of sessions to return
        session_manager: Session manager dependency

    Returns:
        List of sessions
    """
    sessions = await session_manager.list_sessions(project=project, limit=limit)
    return {"sessions": sessions}
