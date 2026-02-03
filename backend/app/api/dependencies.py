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
from app.services.search_index import SearchIndex
from app.services.session_manager import SessionManager
from app.services.vault_manager import VaultManager, VaultManagerConfig

# Module-level cache for AIProcessor singleton
_ai_processor_instance: AIProcessor | None = None


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
    """Get SearchIndex instance."""
    db_path = settings.index_db_path
    return SearchIndex(db_path)


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
