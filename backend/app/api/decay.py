"""API endpoints for decay management."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_search_index
from app.services.decay_classifier import (
    DECAY_TTL,
    DecayClass,
    calculate_expiry,
)
from app.services.search_index import SearchIndex

router = APIRouter(prefix="/api/notes/decay", tags=["decay"])


# --- Pydantic models ---


class DecayRunResponse(BaseModel):
    """Response for POST /run."""

    decayed: int
    protected: int
    expired: int
    message: str


class DecayStats(BaseModel):
    """Response for GET /stats."""

    by_class: dict[str, int]
    expired_count: int
    low_confidence_count: int
    decision_protected_count: int
    average_confidence: float


class DecayOverrideRequest(BaseModel):
    """Request body for PUT /{note_id}."""

    decay_class: DecayClass | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class DecayOverrideResponse(BaseModel):
    """Response for PUT /{note_id}."""

    note_id: int
    decay_class: str
    confidence: float
    expires_at: str | None


# --- Helper ---


async def _ensure_initialized(search_index: SearchIndex) -> None:
    if not search_index.db:
        await search_index.initialize()


# --- Endpoints ---


@router.post("/run", response_model=DecayRunResponse)
async def run_decay(
    search_index: SearchIndex = Depends(get_search_index),
) -> DecayRunResponse:
    """Trigger confidence decay processing."""
    await _ensure_initialized(search_index)

    stats = await search_index.decay_confidence()

    return DecayRunResponse(
        decayed=stats["decayed"],
        protected=stats["protected"],
        expired=stats["expired"],
        message=(
            f"Processed: {stats['decayed']} decayed, "
            f"{stats['protected']} protected, "
            f"{stats['expired']} expired"
        ),
    )


@router.get("/stats", response_model=DecayStats)
async def get_decay_stats(
    search_index: SearchIndex = Depends(get_search_index),
) -> DecayStats:
    """Get decay statistics breakdown."""
    await _ensure_initialized(search_index)

    # Count by decay class
    cursor = await search_index.db.execute(
        "SELECT decay_class, COUNT(*) as count FROM notes GROUP BY decay_class"
    )
    by_class = {row["decay_class"]: row["count"] for row in await cursor.fetchall()}

    # Expired count
    cursor = await search_index.db.execute(
        "SELECT COUNT(*) FROM notes WHERE expires_at IS NOT NULL AND expires_at < datetime('now')"
    )
    expired_count = (await cursor.fetchone())[0]

    # Low confidence count
    cursor = await search_index.db.execute(
        "SELECT COUNT(*) FROM notes WHERE confidence < 0.5"
    )
    low_confidence_count = (await cursor.fetchone())[0]

    # Decision-protected count
    cursor = await search_index.db.execute(
        "SELECT COUNT(DISTINCT note_id) FROM observations WHERE decay_override = 'permanent'"
    )
    decision_protected = (await cursor.fetchone())[0]

    # Average confidence
    cursor = await search_index.db.execute("SELECT AVG(confidence) FROM notes")
    avg_confidence = (await cursor.fetchone())[0] or 1.0

    return DecayStats(
        by_class=by_class,
        expired_count=expired_count,
        low_confidence_count=low_confidence_count,
        decision_protected_count=decision_protected,
        average_confidence=round(avg_confidence, 4),
    )


@router.put("/{note_id}", response_model=DecayOverrideResponse)
async def override_decay(
    note_id: int,
    request: DecayOverrideRequest,
    search_index: SearchIndex = Depends(get_search_index),
) -> DecayOverrideResponse:
    """Manually override decay class and/or confidence for a note."""
    await _ensure_initialized(search_index)

    # Verify note exists
    cursor = await search_index.db.execute(
        "SELECT id, decay_class, confidence, expires_at FROM notes WHERE id = ?",
        (note_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Note not found")

    current_class = row["decay_class"]
    current_confidence = row["confidence"]
    current_expires = row["expires_at"]

    new_class = request.decay_class or current_class
    new_confidence = request.confidence if request.confidence is not None else current_confidence
    new_expires = calculate_expiry(new_class) if request.decay_class else current_expires

    await search_index.db.execute(
        "UPDATE notes SET decay_class = ?, confidence = ?, expires_at = ? WHERE id = ?",
        (new_class, new_confidence, new_expires, note_id),
    )
    await search_index.db.commit()

    return DecayOverrideResponse(
        note_id=note_id,
        decay_class=new_class,
        confidence=new_confidence,
        expires_at=new_expires,
    )
