#!/usr/bin/env python3
"""Obsidian-Memory Python SDK Example.

A simple client library for interacting with the Obsidian-Memory API.

Usage:
    from obsidian_memory_client import ObsidianMemoryClient

    client = ObsidianMemoryClient(
        base_url="http://localhost:8000",
        auth_token="your-token"  # Optional if auth is disabled
    )

    # List notes
    notes = client.list_notes(limit=10)

    # Search notes
    results = client.search("machine learning", project="research")

    # Create a note
    note = client.create_note(
        vault_name="my-vault",
        title="New Note",
        content="# My Note\\n\\nContent here..."
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx


@dataclass
class Note:
    """Represents a note in the knowledge base."""

    id: int
    vault_name: str
    relative_path: str
    permalink: str
    title: str
    note_type: str
    content: str
    tags: list[str]
    project: str | None
    created_at: datetime
    updated_at: datetime
    supersedes: int | None = None
    superseded_by: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Note:
        """Create a Note from API response data."""
        return cls(
            id=data["id"],
            vault_name=data["vault_name"],
            relative_path=data["relative_path"],
            permalink=data["permalink"],
            title=data["title"],
            note_type=data["note_type"],
            content=data.get("content", ""),
            tags=data.get("tags", []),
            project=data.get("project"),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            supersedes=data.get("supersedes"),
            superseded_by=data.get("superseded_by"),
        )


@dataclass
class Project:
    """Represents a project."""

    name: str
    note_count: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        """Create a Project from API response data."""
        return cls(name=data["name"], note_count=data["note_count"])


class ObsidianMemoryError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NotFoundError(ObsidianMemoryError):
    """Resource not found."""

    pass


class AuthenticationError(ObsidianMemoryError):
    """Authentication failed."""

    pass


class RateLimitError(ObsidianMemoryError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int):
        super().__init__(message, 429)
        self.retry_after = retry_after


class ObsidianMemoryClient:
    """Client for the Obsidian-Memory API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        auth_token: str | None = None,
        timeout: float = 30.0,
    ):
        """Initialize the client.

        Args:
            base_url: API base URL
            auth_token: Bearer token for authentication (optional)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def _headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response, raising appropriate errors."""
        if response.status_code == 401:
            raise AuthenticationError("Authentication required", 401)
        if response.status_code == 403:
            raise AuthenticationError("Invalid credentials", 403)
        if response.status_code == 404:
            raise NotFoundError("Resource not found", 404)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError("Rate limit exceeded", retry_after)

        response.raise_for_status()
        return response.json()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request."""
        url = f"{self.base_url}{path}"
        response = self._client.get(url, headers=self._headers(), params=params)
        return self._handle_response(response)

    def _post(self, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a POST request."""
        url = f"{self.base_url}{path}"
        response = self._client.post(url, headers=self._headers(), json=data)
        return self._handle_response(response)

    def _put(self, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PUT request."""
        url = f"{self.base_url}{path}"
        response = self._client.put(url, headers=self._headers(), json=data)
        return self._handle_response(response)

    def _delete(self, path: str) -> dict[str, Any]:
        """Make a DELETE request."""
        url = f"{self.base_url}{path}"
        response = self._client.delete(url, headers=self._headers())
        return self._handle_response(response)

    # Health & Metrics

    def health(self) -> dict[str, Any]:
        """Check API health status."""
        return self._get("/health")

    def metrics(self) -> dict[str, Any]:
        """Get system metrics."""
        return self._get("/metrics")

    # Notes

    def list_notes(
        self,
        vault: str | None = None,
        project: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Note], int]:
        """List notes with optional filtering.

        Args:
            vault: Filter by vault name
            project: Filter by project
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            Tuple of (notes list, total count)
        """
        params = {"limit": limit, "offset": offset}
        if vault:
            params["vault"] = vault
        if project:
            params["project"] = project

        data = self._get("/api/notes", params)
        notes = [Note.from_dict(n) for n in data["notes"]]
        return notes, data["total"]

    def get_note(self, note_id: int) -> Note:
        """Get a note by ID.

        Args:
            note_id: Note ID

        Returns:
            Note object

        Raises:
            NotFoundError: If note doesn't exist
        """
        data = self._get(f"/api/notes/{note_id}")
        return Note.from_dict(data)

    def create_note(
        self,
        vault_name: str,
        title: str,
        content: str,
        relative_path: str | None = None,
        note_type: str = "note",
        project: str | None = None,
        tags: list[str] | None = None,
    ) -> Note:
        """Create a new note.

        Args:
            vault_name: Vault to create note in
            title: Note title
            content: Note content (Markdown)
            relative_path: Path within vault (auto-generated if not provided)
            note_type: Type of note (note, decision, learning, etc.)
            project: Project name
            tags: List of tags

        Returns:
            Created note object
        """
        if relative_path is None:
            # Generate path from title
            safe_title = title.lower().replace(" ", "-")
            relative_path = f"notes/{safe_title}.md"

        data = self._post(
            "/api/notes",
            {
                "vault_name": vault_name,
                "relative_path": relative_path,
                "title": title,
                "content": content,
                "note_type": note_type,
                "project": project,
                "tags": tags or [],
            },
        )
        return Note.from_dict(data)

    def update_note(
        self,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        project: str | None = None,
    ) -> Note:
        """Update a note.

        Args:
            note_id: Note ID to update
            title: New title (optional)
            content: New content (optional)
            tags: New tags (optional)
            project: New project (optional)

        Returns:
            Updated note object
        """
        updates = {}
        if title is not None:
            updates["title"] = title
        if content is not None:
            updates["content"] = content
        if tags is not None:
            updates["tags"] = tags
        if project is not None:
            updates["project"] = project

        data = self._put(f"/api/notes/{note_id}", updates)
        return Note.from_dict(data)

    def delete_note(self, note_id: int) -> None:
        """Delete a note.

        Args:
            note_id: Note ID to delete
        """
        self._delete(f"/api/notes/{note_id}")

    def search(
        self,
        query: str,
        vault: str | None = None,
        project: str | None = None,
        note_type: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Note], int]:
        """Search notes with full-text search.

        Args:
            query: Search query
            vault: Filter by vault
            project: Filter by project
            note_type: Filter by note type
            tags: Filter by tags (all must match)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Tuple of (matching notes, total count)
        """
        search_params = {
            "query": query,
            "limit": limit,
            "offset": offset,
        }
        if vault:
            search_params["vault"] = vault
        if project:
            search_params["project"] = project
        if note_type:
            search_params["note_type"] = note_type
        if tags:
            search_params["tags"] = tags

        data = self._post("/api/notes/search", search_params)
        notes = [Note.from_dict(n) for n in data["notes"]]
        return notes, data["total"]

    def supersede_note(
        self,
        old_note_id: int,
        new_note_id: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Mark a note as superseded by another note.

        Creates bi-directional relationships for knowledge evolution tracking.

        Args:
            old_note_id: ID of the note being replaced
            new_note_id: ID of the replacement note
            reason: Optional reason for supersession

        Returns:
            Dictionary with operation result
        """
        return self._post(
            "/api/notes/supersede",
            {
                "old_note_id": old_note_id,
                "new_note_id": new_note_id,
                "reason": reason,
            },
        )

    # Projects

    def list_projects(self) -> list[Project]:
        """List all projects with note counts.

        Returns:
            List of projects
        """
        data = self._get("/api/projects")
        return [Project.from_dict(p) for p in data["projects"]]

    def get_project_notes(
        self,
        project_name: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get notes for a specific project.

        Args:
            project_name: Project name
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Tuple of (note summaries, total count)
        """
        data = self._get(
            f"/api/projects/{project_name}/notes",
            params={"limit": limit, "offset": offset},
        )
        return data["notes"], data["total_count"]

    # Graph

    def get_graph(self) -> dict[str, Any]:
        """Get the full knowledge graph.

        Returns:
            Dictionary with 'nodes' and 'edges'
        """
        return self._get("/api/graph")

    def get_neighbors(self, node_id: int) -> dict[str, Any]:
        """Get neighbors for a graph node.

        Args:
            node_id: Node ID

        Returns:
            Dictionary with neighbor information
        """
        return self._get(f"/api/graph/nodes/{node_id}/neighbors")

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> ObsidianMemoryClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# Example usage
if __name__ == "__main__":
    # Basic usage example
    with ObsidianMemoryClient(base_url="http://localhost:8000") as client:
        # Check health
        health = client.health()
        print(f"API Status: {health['status']}")

        # List notes
        notes, total = client.list_notes(limit=5)
        print(f"\nFound {total} notes:")
        for note in notes:
            print(f"  - {note.title} ({note.vault_name})")

        # Search example
        results, count = client.search("python", limit=3)
        print(f"\nSearch results for 'python' ({count} total):")
        for note in results:
            print(f"  - {note.title}")

        # Create a note example (commented out to avoid side effects)
        # note = client.create_note(
        #     vault_name="my-vault",
        #     title="API Test Note",
        #     content="# Test Note\n\nCreated via Python SDK.",
        #     tags=["test", "api"],
        # )
        # print(f"\nCreated note: {note.id} - {note.title}")

        # Get graph stats
        graph = client.get_graph()
        print(f"\nKnowledge graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
