"""Application configuration."""

from pathlib import Path
from typing import Any

from pydantic import Field
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

    # AI Processing Configuration
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022", description="Claude model to use"
    )
    ai_processing_enabled: bool = Field(
        default=True, description="Enable AI processing features"
    )
    ai_max_retries: int = Field(
        default=3, ge=1, le=10, description="Maximum retries for AI API calls"
    )
    ai_timeout_seconds: int = Field(
        default=60, ge=10, le=300, description="Timeout for AI API calls in seconds"
    )

    # Logging Configuration
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        """Create settings from a dictionary."""
        return cls(**data)


# Global settings instance
settings = Settings()
