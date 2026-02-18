"""API endpoints for user/project profile synthesis."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field

from app.api.dependencies import (
    get_ai_processor,
    get_search_index,
)
from app.models.note import ProfileNote
from app.services.ai_processor import AIProcessor
from app.services.search_index import SearchIndex

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["Profile"])


class ProfileResponse(BaseModel):
    """Response model for profile endpoint."""

    project: str = Field(..., description="Project identifier")
    static_facts: list[str] = Field(default_factory=list)
    dynamic_patterns: list[str] = Field(default_factory=list)
    key_entities: dict[str, list[str]] = Field(default_factory=dict)
    profile_version: int = Field(default=1)
    last_synthesized: str | None = Field(default=None)
    synthesis_note_count: int = Field(default=0)


class SynthesisResponse(BaseModel):
    """Response model for synthesis trigger."""

    status: str = Field(..., description="Synthesis status")
    message: str = Field(..., description="Status message")
    project: str = Field(..., description="Project being synthesized")


@router.get(
    "/{project}",
    response_model=ProfileResponse,
    summary="Get project profile",
    description="Retrieve the synthesized profile for a project.",
    responses={
        404: {
            "description": "Profile not yet synthesized",
            "content": {
                "application/json": {
                    "example": {"detail": "Profile not synthesized yet for project: my-project"}
                }
            }
        }
    }
)
async def get_profile(
    project: str = Path(..., description="Project identifier"),
    search_index: SearchIndex = Depends(get_search_index),
) -> ProfileResponse:
    """Get the current profile for a project.

    Searches for an existing profile note (note_type='profile') for the
    given project. Returns 404 if no profile has been synthesized yet.
    """
    from app.models.search import SearchQuery

    await _ensure_initialized(search_index)

    # Search for profile note
    query = SearchQuery(
        query="*",
        project=project,
        note_type="profile",
        limit=1,
    )
    results = await search_index.search(query)

    if not results.results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile not synthesized yet for project: {project}",
        )

    result = results.results[0]

    # Parse the profile data from the note content
    import json
    try:
        # Profile notes store JSON in their content
        profile_data = json.loads(result.content) if result.content else {}
    except (json.JSONDecodeError, TypeError):
        profile_data = {}

    return ProfileResponse(
        project=project,
        static_facts=profile_data.get("static_facts", []),
        dynamic_patterns=profile_data.get("dynamic_patterns", []),
        key_entities=profile_data.get("key_entities", {}),
        profile_version=profile_data.get("profile_version", 1),
        last_synthesized=str(result.updated_at) if result.updated_at else None,
        synthesis_note_count=profile_data.get("synthesis_note_count", 0),
    )


@router.post(
    "/{project}/synthesize",
    response_model=SynthesisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger profile synthesis",
    description="Manually trigger profile synthesis for a project.",
)
async def synthesize_profile(
    background_tasks: BackgroundTasks,
    project: str = Path(..., description="Project identifier"),
    search_index: SearchIndex = Depends(get_search_index),
    ai_processor: AIProcessor = Depends(get_ai_processor),
) -> SynthesisResponse:
    """Manually trigger profile synthesis for a project.

    Kicks off synthesis in the background and returns 202 immediately.
    The profile will be available via GET after synthesis completes.
    """
    await _ensure_initialized(search_index)

    background_tasks.add_task(
        _synthesize_and_store,
        project,
        search_index,
        ai_processor,
    )

    return SynthesisResponse(
        status="accepted",
        message=f"Profile synthesis started for project: {project}",
        project=project,
    )


async def _synthesize_and_store(
    project: str,
    search_index: SearchIndex,
    ai_processor: AIProcessor,
) -> None:
    """Background task: synthesize profile and store as note."""
    import json
    from datetime import datetime, timezone
    from app.models.search import IndexedNote

    try:
        profile = await ai_processor.synthesize_profile(project, search_index)

        # Store profile as a special note_type='profile' note
        profile_data = {
            "static_facts": profile.static_facts,
            "dynamic_patterns": profile.dynamic_patterns,
            "key_entities": profile.key_entities,
            "profile_version": profile.profile_version,
            "synthesis_note_count": profile.synthesis_note_count,
        }

        now = datetime.now(timezone.utc)
        permalink = f"profile-{project}"

        indexed_note = IndexedNote(
            note_id=hash(f"profile:{project}") % (2**31),
            vault_name="system",
            relative_path=f".profiles/{project}-profile.md",
            absolute_path=f".profiles/{project}-profile.md",
            permalink=permalink,
            title=f"Profile: {project}",
            content=json.dumps(profile_data),
            note_type="profile",
            project=project,
            tags=["auto-generated", "profile"],
            file_hash=f"profile-{project}-{now.isoformat()}",
            created_at=now,
            updated_at=now,
        )
        await search_index.index_note(indexed_note)
        logger.info(f"Profile stored for project '{project}'")

    except Exception as e:
        logger.error(f"Background profile synthesis failed for '{project}': {e}")


async def _ensure_initialized(search_index: SearchIndex) -> None:
    """Ensure search index is initialized."""
    if not search_index.db:
        await search_index.initialize()
