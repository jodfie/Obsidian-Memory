"""Service layer for business logic."""

from app.services.ai_processor import AIProcessor
from app.services.deduplication_service import DeduplicationService
from app.services.exceptions import (
    DatabaseVaultError,
    DuplicatePathError,
    NoteNotFoundError,
    UnauthorizedError,
)
from app.services.graph_engine import GraphEngine
from app.services.graph_engine_pg import PostgresGraphEngine
from app.services.markdown_parser import MarkdownParser
from app.services.obsidian_exporter import ObsidianExporter
from app.services.pattern_detection_service import PatternDetectionService
from app.services.search_index import SearchIndex
from app.services.search_index_factory import get_search_index
from app.services.search_index_pg import PostgresSearchIndex
from app.services.session_manager import SessionManager
from app.services.sync_service import SyncService
from app.services.sync_state import SyncStateManager
from app.services.vault_manager import VaultManager
from app.services.vault_manager_factory import get_vault_manager
from app.services.vault_manager_pg import PostgresVaultManager
from app.services.wikilink_resolver import WikilinkResolver

__all__ = [
    "AIProcessor",
    "DatabaseVaultError",
    "DeduplicationService",
    "DuplicatePathError",
    "get_search_index",
    "get_vault_manager",
    "GraphEngine",
    "MarkdownParser",
    "NoteNotFoundError",
    "ObsidianExporter",
    "PatternDetectionService",
    "PostgresGraphEngine",
    "PostgresSearchIndex",
    "PostgresVaultManager",
    "SearchIndex",
    "SessionManager",
    "SyncService",
    "SyncStateManager",
    "UnauthorizedError",
    "VaultManager",
    "WikilinkResolver",
]
