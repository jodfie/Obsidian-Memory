"""Data models for session management."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SessionEventType(str, Enum):
    """Type of session event."""

    OBSERVATION = "observation"
    DECISION = "decision"
    ERROR = "error"
    SOLUTION = "solution"
    TOOL_USE = "tool_use"
    FILE_EDIT = "file_edit"
    COMMAND = "command"
    RESEARCH = "research"
    USER_PROMPT = "user_prompt"


class SessionEvent(BaseModel):
    """A single event in a session."""

    event_type: SessionEventType = Field(..., description="Type of event")
    content: str = Field(..., description="Event content")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    metadata: dict = Field(
        default_factory=dict, description="Additional event metadata"
    )
    custom_id: str | None = Field(default=None, description="Optional unique identifier for deduplication (enables upsert)")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp for upserted events")


class Session(BaseModel):
    """A session record."""

    session_id: str = Field(..., description="Unique session identifier")
    project: str | None = Field(default=None, description="Associated project")
    started_at: datetime = Field(default_factory=datetime.now, description="Session start time")
    ended_at: datetime | None = Field(default=None, description="Session end time")
    events: list[SessionEvent] = Field(
        default_factory=list, description="Session events"
    )
    summary: dict | None = Field(default=None, description="AI-generated summary")
    status: str = Field(default="active", description="Session status (active, completed)")
    metadata: dict | None = Field(
        default=None, description="Optional metadata (e.g. last_summarized_at)"
    )


class SessionObserveRequest(BaseModel):
    """Request to observe/add an event to a session."""

    session_id: str = Field(..., description="Session ID")
    event_type: SessionEventType = Field(..., description="Event type")
    content: str = Field(..., description="Event content")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    custom_id: str | None = Field(default=None, description="Optional unique ID for deduplication (enables upsert)")


class SessionContextRequest(BaseModel):
    """Request for session context."""

    session_id: str = Field(..., description="Session ID")
    include_events: bool = Field(default=True, description="Include session events")
    include_summary: bool = Field(default=True, description="Include AI summary if available")
    limit: int = Field(default=50, description="Maximum number of events to return")
