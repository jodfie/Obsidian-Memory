"""Dependency injection for FastAPI endpoints."""

import json
from pathlib import Path

from app.config import settings
from app.services.config_manager import ConfigurationManager
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex
from app.services.vault_manager import VaultManager, VaultManagerConfig


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
