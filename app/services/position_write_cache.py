"""Write-buffer that coalesces per-tick positions updates before flushing to MongoDB"""
import asyncio
import logging
import datetime
from dataclasses import dataclass

from pymongo import InsertOne
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
            self._flush_task = asyncio.create_task(
                self._flush_loop(), name="position-write-cache-flush-task"
            )
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
                await self._flush_all_locked()
                return False  # flushed immediately

        return True  # buffered


    async def flush_all(self) -> None:
        """Flush the entire buffer to MongoDB."""
        async with self._lock:
            await self._flush_all_locked()
        log.info("Write-cache fully flushed to MongoDB")


    # Internal API

    async def _flush_loop(self) -> None:
        """Background task that flushes the buffer to MongoDB on every TTL tick."""
        while True:
            await asyncio.sleep(get_settings().position_cache_ttl_seconds)
            try:
                await self.flush_all()
            except Exception:
                log.exception(f"Unhandled exception during scheduled cache flush.")


    async def _flush_all_locked(self) -> None:
        """
        Write all buffered positions to MongoDB in a single bulk operation. Caller must hold the lock.
        """

        if not self._buffer or self._db is None:
            return

        entries = list(self._buffer.values())
        operations = [
            InsertOne({
                "user_id": e.user_id,
                "x": e.x,
                "y": e.y,
                "timestamp": e.timestamp
            })
            for e in entries
        ]

        # optimistically clear before the await so new puts aren't blocked
        self._buffer.clear()

        try:
            collection = self._db[get_settings().fast_position_collection_name]
            await collection.bulk_write(operations, ordered=False)
            log.debug(f"Flushed {len(entries)} positions to MongoDB")
        except Exception:
            # restore all entries so the next frame tries again
            for entry in entries:
                self._buffer.setdefault(entry.user_id, entry)

            log.exception(f"Failed to flush positions to MongoDB - {len(entries)} entries re-buffered.")
            raise


# module-level singleton
position_write_cache = PositionWriteCache()
