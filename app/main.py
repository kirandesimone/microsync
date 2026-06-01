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
from app.api.positions import router as positions_router


log = logging.getLogger(__name__)

async def start_services() -> None:
    db = await connect_db()
    await ensure_indexes(db)
    position_write_cache.start(db)
    position_read_cache.start(db)
    log.info("Position caches started.")


async def stop_services() -> None:
    await position_write_cache.flush_all()
    log.info("Write-cache flushed on shutdown.")
    disconnect_db()


def load_db_settings(settings: Settings) -> None:
    env_file = find_dotenv(settings.env_mongodb_path)
    load_dotenv(env_file)
    if os.getenv("MONGODB_URI") is not None:
        settings.mongodb_uri = str(os.getenv("MONGODB_URI"))
    if os.getenv("MONGODB_DB_NAME") is not None:
        settings.mongodb_db_name = str(os.getenv("MONGODB_DB_NAME"))


def app_addons(app: FastAPI) -> None:
    app.add_middleware(TimingMiddleware)
    app.include_router(positions_router)
    app.include_router(fast_positions_router)


@asynccontextmanager
async def create_lifespan(_app: FastAPI) -> AsyncGenerator:
    await start_services()
    yield
    await stop_services()
    


def create_app(lifespan=create_lifespan) -> FastAPI:
    settings = get_settings()
    load_db_settings(settings)
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        lifespan=lifespan
    )
    app_addons(app)     
    return app


app = create_app()
