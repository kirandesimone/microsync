"""Application configuration"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Sync Service"""

    app_name: str = "Sync Service"
    app_version: str = "0.1.0"

    host: str = "127.0.0.1"
    port: int = 8000

    position_cache_ttl_seconds: float = 3.0
    position_cache_max_pending: int = 10


def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()
