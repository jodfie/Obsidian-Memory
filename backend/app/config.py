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

    # Authentication Configuration
    require_auth: bool = Field(
        default=False, description="Require Bearer token authentication"
    )
    api_token: str | None = Field(
        default=None, description="Bearer token for API authentication"
    )

    # Cloudflare Access Configuration
    cloudflare_access_enabled: bool = Field(
        default=False, description="Enable Cloudflare Access authentication"
    )
    cloudflare_access_team_domain: str | None = Field(
        default=None, description="Cloudflare Access team domain (e.g., example.cloudflareaccess.com)"
    )
    # Cloudflare API Configuration (for automated setup)
    cloudflare_api_token: str | None = Field(
        default=None, description="Cloudflare API token for managing Access applications"
    )
    cloudflare_account_id: str | None = Field(
        default=None, description="Cloudflare account ID for Zero Trust applications"
    )
    cloudflare_oauth_client_id: str | None = Field(
        default=None, description="Cloudflare Access OAuth client ID for MCP authentication"
    )

    # Sync Configuration
    sync_state_file: Path = Field(
        default=Path.home() / ".obsidian-memory" / "sync_state.json",
        description="Path to sync state file"
    )
    device_id: str | None = Field(
        default=None, description="Device identifier for cross-device sync tracking"
    )

    # Rate Limiting Configuration
    rate_limit_enabled: bool = Field(
        default=True, description="Enable rate limiting"
    )
    rate_limit_requests_per_minute: int = Field(
        default=60, ge=1, le=1000, description="Maximum requests per minute per IP"
    )
    rate_limit_burst: int = Field(
        default=10, ge=1, le=100, description="Burst allowance (extra requests allowed)"
    )

    # Request Validation Configuration
    max_request_size_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        ge=1024,
        description="Maximum request body size in bytes"
    )
    cors_enabled: bool = Field(
        default=True, description="Enable CORS middleware"
    )
    cors_allowed_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins (use ['*'] for all)"
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        """Create settings from a dictionary."""
        return cls(**data)


# Global settings instance
settings = Settings()
