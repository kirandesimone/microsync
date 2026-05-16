"""Read-through cache for player positions.

Gets a snapshot as a plain dict, so client poll requests are a single lookup.
"""

import asyncio
import logging

from pymongo import DESCENDING
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
                self._refresh_loop(), name="position-read-cache-refresh-task"
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


    def get_many(self) -> dict[str, PositionRecord]:
        """Return a copy of the full snapshot: all currently known players."""
        return dict(self._snapshot)


    async def _refresh_loop(self) -> None:
        """Background task that refreshes the cache on a periodic basis."""
        while True:
            await asyncio.sleep(get_settings().read_cache_refresh_seconds)
            try:
                await self._refresh()
            except Exception:
                log.exception(f"Unhandled exception during scheduled cache refresh.")


    async def _refresh(self) -> None:
        """Rebuild the snapshot from MongoDB."""
        if self._db is None:
            return


        pipeline = [
            {"$sort": {"timestamp": DESCENDING}},
            {"$group": {"_id": "$user_id", "doc": {"$first": "$$ROOT"}}}
        ]

        try:
            collection = self._db[get_settings().position_collection_name]
            cursor = collection.aggregate(pipeline)
            new_snapshot: dict[str, PositionRecord] = {}

            async for result in cursor:
                doc = result["doc"]
                doc.pop("_id", None)
                uid = doc["user_id"]
                new_snapshot[uid] = PositionRecord(**doc)

            self._snapshot = new_snapshot
            log.debug(f"Read-cache refreshed with {len(new_snapshot)} users' positions.")
        except Exception:
            log.exception("Read-cache refresh failed — retaining stale snapshot.")


# module-level singleton
position_read_cache = PositionReadCache()
