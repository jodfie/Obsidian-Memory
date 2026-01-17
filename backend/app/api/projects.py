"""Project management API endpoints."""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.dependencies import get_search_index
from app.services.search_index import SearchIndex

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects(
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, list[dict[str, Any]]]:
    """List all projects with note counts.

    Returns:
        Dictionary with 'projects' list containing project names and counts
    """
    await search_index.initialize()
    projects = await search_index.list_projects()

    return {
        "projects": [
            {"name": name, "note_count": count} for name, count in projects
        ]
    }


@router.get("/{project_name}/notes")
async def list_project_notes(
    project_name: str,
    limit: int = 50,
    offset: int = 0,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """List notes for a specific project.

    Args:
        project_name: Name of the project
        limit: Maximum number of notes to return
        offset: Offset for pagination
        search_index: Search index dependency

    Returns:
        Dictionary with 'notes' list and pagination info
    """
    await search_index.initialize()

    # Use get_recent_notes with project filter
    recent_notes = await search_index.get_recent_notes(
        limit=limit + offset,  # Get enough to handle offset
        project=project_name,
    )

    # Apply offset manually (get_recent_notes doesn't support offset)
    if offset > 0 and offset < len(recent_notes):
        recent_notes = recent_notes[offset:]
    elif offset >= len(recent_notes):
        recent_notes = []

    # Limit to requested limit
    if len(recent_notes) > limit:
        recent_notes = recent_notes[:limit]

    # Get total count by querying projects
    projects = await search_index.list_projects()
    project_info = next((p for p in projects if p[0] == project_name), None)
    total_count = project_info[1] if project_info else 0

    return {
        "project": project_name,
        "notes": [
            {
                "note_id": r.note_id,
                "title": r.title,
                "permalink": r.permalink,
                "note_type": r.note_type,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in recent_notes
        ],
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.post("")
async def create_project(
    project_name: str = Body(..., embed=True),
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, str]:
    """Create a new project (implicitly by creating a note with that project).

    Note: Projects are created implicitly when notes are created with a project field.
    This endpoint just validates that the project name is valid.

    Args:
        project_name: Name of the project to create
        search_index: Search index dependency

    Returns:
        Dictionary with project name and status
    """
    if not project_name or not project_name.strip():
        raise HTTPException(status_code=400, detail="Project name cannot be empty")

    # Validate project name (alphanumeric, dash, underscore)
    import re

    if not re.match(r"^[a-zA-Z0-9_-]+$", project_name):
        raise HTTPException(
            status_code=400,
            detail="Project name must contain only alphanumeric characters, dashes, and underscores",
        )

    return {
        "project": project_name,
        "status": "created",
        "message": "Project will be created when first note is added to it",
    }
