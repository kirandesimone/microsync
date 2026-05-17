import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv, find_dotenv

from fastapi import FastAPI

from app.core.config import get_settings
from app.database.mongo import connect_db, disconnect_db, ensure_indexes
from app.middleware.timing import TimingMiddleware
from app.services.position_read_cache import position_read_cache
from app.services.position_write_cache import position_write_cache
from app.api.fast_positions import router as fast_positions_router


log = logging.getLogger(__name__)


@asynccontextmanager
async def create_lifespan(_app: FastAPI) -> AsyncGenerator:
    # Startup
    db = await connect_db()
    await ensure_indexes(db)
    position_write_cache.start(db)
    position_read_cache.start(db)
    log.info("Position caches started.")

    yield

    # Shutdown
    await position_write_cache.flush_all()
    log.info("Write-cache flushed on shutdown.")
    disconnect_db()


def create_app(lifespan=create_lifespan) -> FastAPI:
    settings = get_settings()

    env_file = find_dotenv(settings.env_mongodb_path)
    load_dotenv(env_file)
    if os.getenv("MONGODB_URI") is not None:
        settings.mongodb_uri = str(os.getenv("MONGODB_URI"))
    if os.getenv("MONGODB_DB_NAME") is not None:
        settings.mongodb_db_name = str(os.getenv("MONGODB_DB_NAME"))

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        lifespan=lifespan
    )

    app.add_middleware(TimingMiddleware)
    app.include_router(fast_positions_router)

    @app.get("/status", tags=["status"], include_in_schema=False)
    async def status() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
