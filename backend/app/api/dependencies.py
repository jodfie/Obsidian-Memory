"""Dependency injection for FastAPI endpoints."""

import json
from pathlib import Path

from fastapi import Depends

from app.config import settings
from app.services.ai_processor import AIProcessor
from app.services.config_manager import ConfigurationManager
from app.services.markdown_parser import MarkdownParser
from app.services.deduplication_service import DeduplicationService
from app.services.pattern_detection_service import PatternDetectionService
from app.services.profile_tracker import ProfileSynthesisTracker
from app.services.search_index import SearchIndex
from app.services.session_manager import SessionManager
from app.services.vault_manager import VaultManager, VaultManagerConfig

# Module-level singletons
_ai_processor_instance: AIProcessor | None = None
_search_index_instance: SearchIndex | None = None
_profile_tracker_instance: ProfileSynthesisTracker | None = None


def get_ai_processor() -> AIProcessor:
    """Get AIProcessor singleton instance.

    Returns a singleton to avoid reinitializing the AI client on every request.
    The AIProcessor is stateless, so sharing is safe.
    """
    global _ai_processor_instance
    if _ai_processor_instance is None:
        _ai_processor_instance = AIProcessor()
    return _ai_processor_instance


def get_vault_manager() -> VaultManager:
    """Get VaultManager instance."""
    config_file = settings.config_file
    if config_file.exists():
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
        config = VaultManagerConfig(**data)
    else:
        # Create default empty config
        config = VaultManagerConfig(vaults=[])
    return VaultManager(config)


def get_markdown_parser() -> MarkdownParser:
    """Get MarkdownParser instance."""
    return MarkdownParser()


def get_search_index() -> SearchIndex:
    """Get SearchIndex singleton instance.

    Returns the same SearchIndex across all requests so the file watcher
    and API share one SQLite connection, avoiding WAL contention.
    Re-creates if the configured DB path has changed (e.g. in tests).
    """
    global _search_index_instance
    current_path = settings.index_db_path
    if (
        _search_index_instance is None
        or _search_index_instance.db_path != current_path
    ):
        _search_index_instance = SearchIndex(current_path)
    return _search_index_instance


def get_config_manager() -> ConfigurationManager:
    """Get ConfigurationManager instance."""
    return ConfigurationManager(config_path=settings.config_file)


def get_session_manager() -> SessionManager:
    """Get SessionManager instance."""
    return SessionManager()


def get_pattern_detection_service(
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
    ai_processor: AIProcessor = Depends(get_ai_processor),
    session_manager: SessionManager = Depends(get_session_manager),
) -> PatternDetectionService:
    """Get PatternDetectionService instance."""
    return PatternDetectionService(
        search_index=search_index,
        vault_manager=vault_manager,
        markdown_parser=markdown_parser,
        ai_processor=ai_processor,
        session_manager=session_manager,
    )


def get_deduplication_service(
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
    ai_processor: AIProcessor = Depends(get_ai_processor),
) -> DeduplicationService:
    """Get DeduplicationService instance."""
    return DeduplicationService(
        search_index=search_index,
        vault_manager=vault_manager,
        markdown_parser=markdown_parser,
        ai_processor=ai_processor,
    )


def get_profile_tracker() -> ProfileSynthesisTracker:
    """Get ProfileSynthesisTracker singleton instance."""
    global _profile_tracker_instance
    if _profile_tracker_instance is None:
        _profile_tracker_instance = ProfileSynthesisTracker()
    return _profile_tracker_instance
