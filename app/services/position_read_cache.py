"""Read-through cache for player positions.

Gets a snapshot as a plain dict, so client poll requests are a single lookup.
"""

import asyncio
import logging

from datetime import datetime, timezone

from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings
from app.schemas.position import PositionRecord

log = logging.getLogger(__name__)


class PositionReadCache:
    """
    Singleton read-through cache. Created once at module level, shared across requests with `position_read_cache`
    """

    def __init__(self) -> None:
        # snapshot: user_id -> latest PositionRecord
        self._snapshot: dict[str, PositionRecord] = {}
        self._refresh_task: asyncio.Task | None = None
        self._db: AsyncDatabase | None = None


    def start(self, db: AsyncDatabase) -> None:
        self._db = db
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(
                self._refresh_loop(), name="position-cache-refresh-task"
            )
            log.info(
                "Position read-cache started (TTL=%.1fs)",
                get_settings().read_cache_refresh_seconds
            )


    async def stop(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass


    def get_many(self, user_ids: list[str]) -> dict[str, PositionRecord]:
        """Return the snapshot for the requested user_ids.
        Only user_ids present in the snapshot are included in the result"""
        return {uid: self._snapshot[uid] for uid in user_ids if uid in self._snapshot}


    async def _refresh_loop(self) -> None:
        """Background task that refreshes the cache on a periodic basis."""
        pass


    async def _fetch_from_db(self, user_ids: list[str]) -> dict[str, PositionRecord]:
    async def _fetch_from_db(self, user_id: str) -> PositionRecord | None:
        """Fetch the latest position docs for each user_id is a single aggregate query."""
        assert self._db is not None

        col = self._db[f"positions_{user_id}"]
        doc = await col.find_one({}, {"_id": 0}, sort=[("timestamp", -1)])

        return PositionRecord(**doc) if doc else None


# module-level singleton
position_read_cache = PositionReadCache()
