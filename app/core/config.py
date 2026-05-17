"""Application configuration"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the Sync Service"""

    app_name: str = "Client Position Sync Service"
    app_version: str = "0.1.0"
    app_description: str = "Service that syncs client position data to a MongoDB database and attached clients"

    host: str = "127.0.0.1"
    port: int = 8000

    # Write / Read Cache
    position_cache_ttl_seconds: float = 3.0
    position_cache_max_pending: int = 10
    read_cache_refresh_seconds: float = 2.0

    # MongoDB
    env_mongodb_path: str = ".env.mongodb"
    mongodb_uri: str = ""
    mongodb_db_name: str = ""
    position_collection_name: str = "positions" + "_"


def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()
