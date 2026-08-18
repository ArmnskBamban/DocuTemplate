"""Application configuration via environment variables.

All settings are optional and ship with safe defaults. Settings are read from
the environment (and an optional ``.env`` file) so the core engine never
hardcodes tunables. No secrets are required: the optional AI layer is disabled
by default and the engine works fully without it.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for PraktiKit.

    Values can be overridden through environment variables (case-insensitive) or
    a ``.env`` file next to the project. Use ``Settings()`` to get a singleton;
    import it via :func:`get_settings` for caching.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Upload limits ---
    max_upload_size: int = Field(
        default=25 * 1024 * 1024, description="Maximum accepted upload size in bytes."
    )

    # --- Processing ---
    temp_directory: str = Field(
        default="", description="Base directory for temporary working files (empty = system temp)."
    )
    session_ttl: int = Field(default=1800, description="Idle seconds before a session expires.")

    # --- Detection thresholds ---
    auto_threshold: float = Field(
        default=0.90,
        description="Confidence at/above which an element is handled automatically.",
    )
    review_threshold: float = Field(
        default=0.70,
        description="Confidence at/above which an element is auto-handled but flagged for review.",
    )

    # --- Safety ---
    strict_leak_check: bool = Field(
        default=True, description="If true, generation fails when old-content leaks are detected."
    )
    leak_similarity_threshold: float = Field(
        default=0.6,
        description="Minimum shared-shingle ratio (0.0-1.0) to flag text as a content leak.",
    )

    # --- Optional AI layer (off by default; core works fully without it) ---
    ai_enabled: bool = Field(default=False, description="Enable the optional LLM classifier.")
    ai_provider: str = Field(default="", description="LLM provider name (e.g. 'openai').")
    ai_model: str = Field(default="", description="LLM model identifier.")

    # --- Logging ---
    log_level: str = Field(default="INFO", description="Root log level.")

    def temp_base(self) -> Path:
        """Resolve the base temp directory (system temp when unset)."""
        return Path(self.temp_directory).expanduser() if self.temp_directory else None


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached process-wide :class:`Settings` instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Drop the cached settings (useful for tests that mutate the environment)."""
    global _settings
    _settings = None
