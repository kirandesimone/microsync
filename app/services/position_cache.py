"""Write-buffer that coalesces per-tick positions updates before flushing to MongoDB"""
import asyncio
import datetime
from dataclasses import dataclass

from pymongo.asynchronous.database import AsyncDatabase


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
        # Guard, only run if task is not already running
        #   Create task for _flush_loop()
        pass


    async def stop(self) -> None:
        """Cancel the background task, called before flush_all on shutdown."""
        # Guard, only run if task is running
        #   Cancel task
        pass


    # Public API

    async def put(self) -> bool:
        """
        Buffer a position update

        :return: True if the update was buffered, False if the buffer is full
        """
        # Get async lock
        #   Get user's existing and pending position from buffer
        #   Append new position to user's buffer
        #   Check if buffer is full
        #      True: Push to MongoDB, return False
        #   False: Return True
        pass


    async def flush_all(self) -> None:
        """Flush the entire buffer to MongoDB."""
        # Get async lock
        #   Flush all users' positions to MongoDB'
        pass


    # Internal API

    async def _flush_loop(self) -> None:
        """Background task that flushes the buffer to MongoDB on every TTL tick."""
        # Await for next tick
        #   then call flush_all()
        pass


    async def _flush_user(self, user_id: str) -> None:
        """Write a singer user's buffered position to MongoDB. Caller must hold the lock."""
        # Get user's current buffered position
        #   Guard: if no buffered position, early return
        # Await on MongoDB insert
        pass


# module-level singleton
position_write_cache = PositionWriteCache()
