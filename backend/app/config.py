"""Application configuration."""

from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Configuration
    api_title: str = "Obsidian-Memory"
    api_version: str = "0.1.0"
    debug: bool = False

    # Vault Configuration
    config_file: Path = Path.home() / ".obsidian-memory" / "config.json"
    default_vault: str | None = None

    # Search Index Configuration
    index_db_path: Path = Path.home() / ".obsidian-memory" / "index.db"

    # Logging Configuration
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        """Create settings from a dictionary."""
        return cls(**data)


# Global settings instance
settings = Settings()
