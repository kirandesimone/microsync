"""Async MongoDB client lifecycle using the PyMongo Async API (AsyncMongoClient)."""
import logging

from pymongo import AsyncMongoClient, DESCENDING, IndexModel
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings

log = logging.getLogger(__name__)

_client: AsyncMongoClient | None = None
_db: AsyncDatabase | None = None


async def connect_db() -> AsyncDatabase:
    """Open the MongoDB connection, ping to verify, and return the handle"""
    global _client, _db
    settings = get_settings()

    log.info(f"Connecting to MongoDB at {settings.mongodb_uri}...")
    _client = AsyncMongoClient(settings.mongodb_uri)
    if _client is None:
        raise RuntimeError("Failed to create MongoDB client")
    await _client.aconnect()

    _db = _client[settings.mongodb_db_name]
    if _db is None:
        raise RuntimeError("Failed to get MongoDB database")
    await _db.command("ping")
    log.info(f"MongoDB connection established with (db={settings.mongodb_db_name})")

    return _db


def disconnect_db() -> None:
    """Close the MongoDB connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        log.info("MongoDB connection closed")


async def ensure_indexes(db: AsyncDatabase) -> None:
    """
    Create indexes on the MongoDB collection.

    (user_id, timestamp DESC): covers the read-cache aggregation and
    any future single-player lookups.

    TTL on timestamp: automatically expires documents after 30 minutes
    so the collection doesn't grow unbounded.
    """

    collection = db[get_settings().fast_position_collection_name]
    await collection.create_indexes([
        IndexModel([("user_id", DESCENDING), ("timestamp", DESCENDING)]),
        IndexModel([("timestamp", DESCENDING)], expireAfterSeconds=1800, name="ttl_timestamp")
    ])
    log.info(f"Indexes ensured on MongoDB collection {collection.name}")


async def get_db():
    """FastAPI dependency: yields the active AsyncDatabase handle."""
    if _db is None:
        raise RuntimeError("MongoDB connection not established")
    yield _db
