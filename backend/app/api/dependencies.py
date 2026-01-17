"""API dependencies for dependency injection."""

from pathlib import Path

from app.config import settings
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex
from app.services.vault_manager import VaultManager, VaultManagerConfig


async def get_vault_manager() -> VaultManager:
    """Get VaultManager instance."""
    # TODO: Load from config file
    # For now, return a minimal config
    config = VaultManagerConfig(vaults=[], default_vault=None)
    return VaultManager(config)


def get_markdown_parser() -> MarkdownParser:
    """Get MarkdownParser instance."""
    return MarkdownParser()


# Global search index instance (singleton pattern)
_search_index: SearchIndex | None = None


async def get_search_index() -> SearchIndex:
    """Get SearchIndex instance (singleton)."""
    global _search_index
    if _search_index is None:
        db_path = settings.config_file.parent / "index.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _search_index = SearchIndex(db_path)
        await _search_index.initialize()
    return _search_index
