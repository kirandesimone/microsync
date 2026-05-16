"""Write-buffer that coalesces per-tick positions updates before flushing to MongoDB"""
import asyncio
import logging
import datetime
from dataclasses import dataclass

from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class _BufferedPosition:
    user_id: str
    x: float
    y: float
    timestamp: datetime
    pending_count: int = 0


class PositionWriteCache:
    """
    Singleton write-buffer. Created once at module level, shared across requests with `position_write_cache`
    """

    def __init__(self) -> None:
        self._buffer: dict[str, _BufferedPosition] = {}
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._db: AsyncDatabase | None = None


    def start(self, db: AsyncDatabase) -> None:
        """Called once at app startup after the DB connection is established"""
        self._db = db
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_loop(), name="position-cache-flush-task")
            log.info(
                "Position write-cache started (TTL=%.1fs, max_pending=%d)",
                get_settings().position_cache_ttl_seconds,
                get_settings().position_cache_max_pending
            )


    async def stop(self) -> None:
        """Cancel the background task, called before flush_all on shutdown."""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass


    # Public API

    async def put(self, user_id: str, x: float, y: float, timestamp: datetime) -> bool:
        """
        Buffer a position update

        :return: True if the update was buffered, False if the buffer is full
        """
        async with self._lock:
            existing = self._buffer.get(user_id)
            pending = (existing.pending_count + 1) if existing else 1

            self._buffer[user_id] = _BufferedPosition(
                user_id=user_id,
                x=x,
                y=y,
                timestamp=timestamp,
                pending_count=pending
            )

            if pending >= get_settings().position_cache_max_pending:
                log.debug(f"Max pending reached for {user_id} -> forcing flush")
                await self._flush_user(user_id)
                return False  # flushed immediately

        return True  # buffered


    async def flush_all(self) -> None:
        """Flush the entire buffer to MongoDB."""
        async with self._lock:
            user_ids = list(self._buffer.keys())
            for uid in user_ids:
                await self._flush_user(uid)
        log.info(f"Flushed {len(user_ids)} users' positions to MongoDB")


    # Internal API

    async def _flush_loop(self) -> None:
        """Background task that flushes the buffer to MongoDB on every TTL tick."""
        while True:
            await asyncio.sleep(get_settings().position_cache_ttl_seconds)
            try:
                await self.flush_all()
            except Exception:
                log.exception(f"Unhandled exception during scheduled cache flush.")


    async def _flush_user(self, user_id: str) -> None:
        """Write a singer user's buffered position to MongoDB. Caller must hold the lock."""
        entry = self._buffer.pop(user_id, None)
        if entry is None or self._db is None:
            return

        collection = self._db[f"positions_{user_id}"]
        document = {
            "user_id": entry.user_id,
            "x": entry.x,
            "y": entry.y,
            "timestamp": entry.timestamp
        }
        try:
            await collection.insert_one(document)
            log.debug(f"Flushed position for {user_id} to MongoDB")
        except Exception:
            # re-buffer the entry so the data isn't lost; the next flush will retry (US-1 reliability attribute)
            self._buffer[user_id] = entry
            log.exception(f"Failed to flush position for {user_id} -> re-buffering")
            raise


# module-level singleton
position_write_cache = PositionWriteCache()
