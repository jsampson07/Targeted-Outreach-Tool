from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / `.env`.

    Field names are snake_case in Python; pydantic-settings maps them to
    the matching UPPER_SNAKE env vars (DATABASE_URL, JWT_SECRET_KEY, …).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    # Complex types (list[str]) must be a JSON-encoded string in .env if
    # overriding the default — e.g. CORS_ALLOWED_ORIGINS='["http://localhost:5173","http://localhost:3000"]'.
    # A bare comma-separated value will not parse correctly under pydantic-settings.
    cors_allowed_origins: list[str] = ["http://localhost:5173"]
    # Default stays mock so routine local use never spends Hunter credits.
    contact_provider: Literal["mock", "hunter"] = "mock"
    hunter_api_key: str | None = None
    # LLM extraction (ARCHITECTURE.md §3). Key optional so non-LLM routes
    # still boot; LLMClient fails clearly at call time if missing.
    anthropic_api_key: str | None = None
    # Haiku: cost-appropriate for structured extraction; not the most capable model.
    llm_model: str = "claude-haiku-4-5"
    # Retries after the first parse/validation failure (1 → one retry, two attempts).
    llm_max_retries: int = 1


@lru_cache
def get_settings() -> Settings:
    """Return a process-cached Settings instance (read once, not per call)."""
    return Settings()
