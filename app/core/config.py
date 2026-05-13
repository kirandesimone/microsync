"""Application configuration"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the Sync Service"""

    app_name: str = "Sync Service"
    app_version: str = "0.1.0"

    host: str = "127.0.0.1"
    port: int = 8000

    class Config:
        env_file = ".env.mongodb"  # create and populate .env.mongodb file locally, do not commit to git


def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()
