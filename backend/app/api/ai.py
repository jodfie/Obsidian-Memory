"""AI-related API endpoints (pattern detection, etc.)."""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import (
    get_deduplication_service,
    get_pattern_detection_service,
    get_search_index,
)
from app.services.deduplication_service import DeduplicationService
from app.services.pattern_detection_service import PatternDetectionService
from app.services.search_index import SearchIndex

router = APIRouter(prefix="/api/ai", tags=["ai"])


class DetectPatternsRequest(BaseModel):
    """Request body for triggering pattern detection."""

    note_ids: list[int] | None = Field(
        default=None,
        description="Note IDs to analyze (omit for recent notes)",
    )
    session_ids: list[str] | None = Field(
        default=None,
        description="Session IDs whose summaries to include",
    )
    limit_notes: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Max notes when note_ids not provided",
    )


class DetectPatternsResponse(BaseModel):
    """Response for pattern detection."""

    patterns: list[dict[str, Any]]
    from_cache: bool
    count: int


@router.post("/detect-patterns", response_model=DetectPatternsResponse)
async def detect_patterns(
    request: DetectPatternsRequest = Body(...),
    pattern_service: PatternDetectionService = Depends(get_pattern_detection_service),
) -> DetectPatternsResponse:
    """Trigger pattern detection with optional note/session filters.

    Analyzes notes (and optional session summaries) to find recurring patterns.
    Results are cached by content hash to avoid redundant AI calls.
    """
    patterns, from_cache = await pattern_service.analyze_patterns(
        note_ids=request.note_ids,
        session_ids=request.session_ids,
        limit_notes=request.limit_notes,
    )
    return DetectPatternsResponse(
        patterns=patterns,
        from_cache=from_cache,
        count=len(patterns),
    )


@router.get("/patterns")
async def get_patterns(
    category: str | None = None,
    min_confidence: float = 0.0,
    limit: int = 100,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """List detected patterns with optional filtering."""
    await search_index.initialize()
    patterns = await search_index.get_patterns(
        category=category,
        min_confidence=min_confidence,
        limit=limit,
    )
    return {"patterns": patterns, "count": len(patterns)}


@router.get("/patterns/{pattern_id}")
async def get_pattern(
    pattern_id: int,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """Get a single pattern by ID."""
    await search_index.initialize()
    pattern = await search_index.get_pattern_by_id(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return pattern


@router.get("/patterns/{pattern_id}/notes")
async def get_notes_for_pattern(
    pattern_id: int,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """Get notes that exhibit a pattern."""
    await search_index.initialize()
    pattern = await search_index.get_pattern_by_id(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    notes = await search_index.get_notes_for_pattern(pattern_id)
    return {"pattern_id": pattern_id, "notes": notes, "count": len(notes)}


# -------------------------------------------------------------------------
# Deduplication endpoints
# -------------------------------------------------------------------------

class FindDuplicatesRequest(BaseModel):
    """Request body for triggering duplicate analysis."""

    vault_name: str | None = Field(
        default=None,
        description="Limit to vault (omit for all vaults)",
    )
    limit_pairs: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Max note pairs to analyze",
    )


@router.post("/find-duplicates")
async def find_duplicates(
    request: FindDuplicatesRequest = Body(...),
    dedup_service: DeduplicationService = Depends(get_deduplication_service),
) -> dict[str, Any]:
    """Trigger deduplication analysis; store suggestions."""
    suggestions, pairs_analyzed = await dedup_service.analyze_candidates(
        vault_name=request.vault_name,
        limit_pairs=request.limit_pairs,
    )
    return {
        "suggestions": suggestions,
        "count": len(suggestions),
        "pairs_analyzed": pairs_analyzed,
    }


@router.get("/duplicates")
async def get_duplicates(
    status: str | None = "pending",
    limit: int = 100,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """List deduplication suggestions (default: pending)."""
    await search_index.initialize()
    suggestions = await search_index.get_dedup_suggestions(status=status, limit=limit)
    return {"suggestions": suggestions, "count": len(suggestions)}


@router.get("/duplicates/{suggestion_id}")
async def get_duplicate(
    suggestion_id: int,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """Get a single dedup suggestion by ID."""
    await search_index.initialize()
    suggestion = await search_index.get_dedup_suggestion_by_id(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return suggestion


@router.put("/duplicates/{suggestion_id}/accept")
async def accept_duplicate(
    suggestion_id: int,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """Mark suggestion as accepted (caller should then merge/link via POST /api/notes/merge)."""
    await search_index.initialize()
    suggestion = await search_index.get_dedup_suggestion_by_id(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Suggestion already {suggestion['status']}")
    ok = await search_index.update_dedup_suggestion_status(suggestion_id, "accepted")
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to update status")
    return {"message": "Suggestion accepted", "suggestion_id": suggestion_id}


@router.put("/duplicates/{suggestion_id}/reject")
async def reject_duplicate(
    suggestion_id: int,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """Mark suggestion as rejected."""
    await search_index.initialize()
    suggestion = await search_index.get_dedup_suggestion_by_id(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Suggestion already {suggestion['status']}")
    ok = await search_index.update_dedup_suggestion_status(suggestion_id, "rejected")
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to update status")
    return {"message": "Suggestion rejected", "suggestion_id": suggestion_id}
