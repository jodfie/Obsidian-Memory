"""Factory function for vault manager instantiation.

This module provides a factory function that returns the appropriate vault manager
implementation based on the configured database mode.

Usage:
    from app.config import settings
    from app.db import get_db
    from app.services.vault_manager_factory import get_vault_manager

    @app.get("/notes")
    async def list_notes(db: AsyncSession = Depends(get_db)):
        vault_manager = get_vault_manager(settings.db_mode, session=db)
        # For Postgres mode, vault_manager is PostgresVaultManager
        # For SQLite mode, vault_manager is VaultManager (file-based)
"""

from typing import TYPE_CHECKING, overload

from app.config import DatabaseMode

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.vault import VaultManagerConfig
    from app.services.vault_manager import VaultManager
    from app.services.vault_manager_pg import PostgresVaultManager


@overload
def get_vault_manager(
    db_mode: DatabaseMode,
    *,
    session: "AsyncSession",
    config: None = None,
) -> "PostgresVaultManager": ...


@overload
def get_vault_manager(
    db_mode: DatabaseMode,
    *,
    session: None = None,
    config: "VaultManagerConfig",
) -> "VaultManager": ...


def get_vault_manager(
    db_mode: DatabaseMode,
    *,
    session: "AsyncSession | None" = None,
    config: "VaultManagerConfig | None" = None,
) -> "PostgresVaultManager | VaultManager":
    """Get the appropriate vault manager implementation.

    Returns a PostgresVaultManager for Postgres mode (Supabase) or a file-based
    VaultManager for SQLite mode (local development).

    Args:
        db_mode: The database mode from settings (DatabaseMode.SQLITE or DatabaseMode.POSTGRES).
        session: SQLAlchemy AsyncSession (required for Postgres mode).
        config: VaultManagerConfig (required for SQLite mode).

    Returns:
        PostgresVaultManager for Postgres mode, VaultManager for SQLite mode.

    Raises:
        ValueError: If required arguments are missing for the selected mode.

    Examples:
        # Postgres mode (Supabase)
        vault_manager = get_vault_manager(
            DatabaseMode.POSTGRES,
            session=db_session,
        )
        notes = await vault_manager.list_notes(user_id=user.id)

        # SQLite mode (file-based)
        vault_manager = get_vault_manager(
            DatabaseMode.SQLITE,
            config=vault_config,
        )
        vault_file = await vault_manager.read_file("path/to/note.md")
    """
    if db_mode == DatabaseMode.POSTGRES:
        if session is None:
            raise ValueError(
                "Postgres mode requires an AsyncSession. "
                "Pass session=db_session to get_vault_manager()."
            )

        from app.services.vault_manager_pg import PostgresVaultManager

        return PostgresVaultManager(session)

    elif db_mode == DatabaseMode.SQLITE:
        if config is None:
            raise ValueError(
                "SQLite mode requires a VaultManagerConfig. "
                "Pass config=vault_config to get_vault_manager()."
            )

        from app.services.vault_manager import VaultManager

        return VaultManager(config)

    else:
        raise ValueError(f"Unknown database mode: {db_mode}")


# Convenience type alias for type hints
VaultManagerType = "PostgresVaultManager | VaultManager"
