"""API endpoints for on-demand decision extraction."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import get_ai_processor, get_markdown_parser, get_search_index
from app.services.ai_processor import AIProcessor, ai_decision_to_observation
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex

router = APIRouter(prefix="/api/notes", tags=["decisions"])


# --- Pydantic models ---


class ExtractDecisionsRequest(BaseModel):
    """Request body for single-note decision extraction."""

    method: Literal["regex", "ai", "both"] = Field(default="regex")
    dry_run: bool = Field(default=False)


class ExtractDecisionsResponse(BaseModel):
    """Response for single-note decision extraction."""

    extracted: int
    decisions: list[dict]
    dry_run: bool


class BulkExtractRequest(BaseModel):
    """Request body for bulk decision extraction."""

    method: Literal["regex", "ai", "both"] = Field(default="regex")
    vault: str | None = None
    project: str | None = None
    dry_run: bool = Field(default=False)
    reprocess: bool = Field(default=False)


class BulkExtractResponse(BaseModel):
    """Response for bulk decision extraction."""

    notes_scanned: int
    extracted: int
    decisions: list[dict]
    dry_run: bool


# --- Helper ---


async def _ensure_initialized(search_index: SearchIndex) -> None:
    if not search_index.db:
        await search_index.initialize()


async def _get_existing_observations(search_index: SearchIndex, note_id: int) -> list:
    """Get existing observations for a note from the DB."""
    from app.models.note import Observation, ObservationCategory

    cursor = await search_index.db.execute(
        "SELECT category, content FROM observations WHERE note_id = ?",
        (note_id,),
    )
    rows = await cursor.fetchall()
    return [
        Observation(
            category=ObservationCategory(row["category"]),
            content=(row["content"] or ""),
            tags=[],
            line_number=0,
        )
        for row in rows
    ]


async def _extract_for_note(
    note_id: int,
    content: str,
    title: str,
    method: str,
    parser: MarkdownParser,
    ai_processor: AIProcessor,
    existing_obs: list,
) -> list[dict]:
    """Run extraction method(s) on a single note's content."""
    decisions: list[dict] = []

    if method in ("regex", "both"):
        regex_results = parser.extract_decisions_from_prose(content, existing_obs)
        for obs in regex_results:
            decisions.append({
                "content": obs.content,
                "context": obs.context,
                "line_number": obs.line_number,
                "method": "regex",
            })

    if method in ("ai", "both"):
        ai_results = await ai_processor.extract_decisions(content, title)
        for d in ai_results:
            decisions.append({
                "content": d.content,
                "rationale": d.rationale,
                "confidence": d.confidence,
                "decision_type": d.decision_type,
                "method": "ai",
            })

    return decisions


async def _persist_decisions(
    search_index: SearchIndex,
    note_id: int,
    decisions: list[dict],
) -> None:
    """Store extracted decisions as observations."""
    for decision in decisions:
        await search_index.db.execute(
            """
            INSERT INTO observations(
                note_id, category, content, context, auto_extracted, decay_override
            ) VALUES (?, 'decision', ?, ?, 1, 'permanent')
            """,
            (note_id, decision["content"], decision.get("rationale") or decision.get("context")),
        )
    await search_index.db.commit()


# --- Endpoints ---


@router.post("/{note_id}/extract-decisions", response_model=ExtractDecisionsResponse)
async def extract_decisions_single(
    note_id: int,
    request: ExtractDecisionsRequest,
    search_index: SearchIndex = Depends(get_search_index),
    parser: MarkdownParser = Depends(get_markdown_parser),
    ai_processor: AIProcessor = Depends(get_ai_processor),
) -> ExtractDecisionsResponse:
    """Extract decisions from a single note."""
    await _ensure_initialized(search_index)

    # Read directly from DB (get_note_by_id returns empty content due to FTS)
    cursor = await search_index.db.execute(
        "SELECT id, title, content FROM notes WHERE id = ?", (note_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Note not found")

    existing_obs = await _get_existing_observations(search_index, note_id)

    decisions = await _extract_for_note(
        note_id=note_id,
        content=(row["content"] or ""),
        title=row["title"],
        method=request.method,
        parser=parser,
        ai_processor=ai_processor,
        existing_obs=existing_obs,
    )

    if not request.dry_run and decisions:
        await _persist_decisions(search_index, note_id, decisions)

    return ExtractDecisionsResponse(
        extracted=len(decisions),
        decisions=decisions[:10],
        dry_run=request.dry_run,
    )


@router.post("/extract-decisions", response_model=BulkExtractResponse)
async def extract_decisions_bulk(
    request: BulkExtractRequest,
    search_index: SearchIndex = Depends(get_search_index),
    parser: MarkdownParser = Depends(get_markdown_parser),
    ai_processor: AIProcessor = Depends(get_ai_processor),
) -> BulkExtractResponse:
    """Bulk decision extraction with optional vault/project filters."""
    await _ensure_initialized(search_index)

    # Build filter query
    conditions = []
    params: list = []

    if request.vault:
        conditions.append("vault_name = ?")
        params.append(request.vault)
    if request.project:
        conditions.append("project = ?")
        params.append(request.project)

    where = " AND ".join(conditions) if conditions else "1=1"

    cursor = await search_index.db.execute(
        f"SELECT id, title, content FROM notes WHERE {where}",
        params,
    )
    rows = await cursor.fetchall()

    notes_scanned = 0
    all_decisions: list[dict] = []

    for row in rows:
        nid = row["id"]
        notes_scanned += 1

        # Skip already-processed notes unless reprocess requested
        if not request.reprocess:
            obs_cursor = await search_index.db.execute(
                "SELECT 1 FROM observations WHERE note_id = ? AND auto_extracted = 1 AND category = 'decision' LIMIT 1",
                (nid,),
            )
            if await obs_cursor.fetchone():
                continue

        existing_obs = await _get_existing_observations(search_index, nid)

        decisions = await _extract_for_note(
            note_id=nid,
            content=(row["content"] or ""),
            title=row["title"],
            method=request.method,
            parser=parser,
            ai_processor=ai_processor,
            existing_obs=existing_obs,
        )

        if not request.dry_run and decisions:
            await _persist_decisions(search_index, nid, decisions)

        all_decisions.extend(decisions)

    return BulkExtractResponse(
        notes_scanned=notes_scanned,
        extracted=len(all_decisions),
        decisions=all_decisions[:10],
        dry_run=request.dry_run,
    )
