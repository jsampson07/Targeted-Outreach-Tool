from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    """Return a process-cached Settings instance (read once, not per call)."""
    return Settings()
