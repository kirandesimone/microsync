"""Tests for the position write-cache"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import get_settings
from app.services.position_write_cache import PositionWriteCache, _BufferedPosition


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_db(bulk_write_side_effect=None):
    collection = MagicMock()
    collection.bulk_write = AsyncMock(side_effect=bulk_write_side_effect)
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=collection)

    return db, collection


@pytest.fixture
def cache():
    """Fresh cache instance per test to avoid a shared singleton state"""
    return PositionWriteCache()


class TestPositionWriteCache_Put:

    @pytest.mark.asyncio
    async def test_first_put_is_buffered(self, cache):
        """First write for a user should be buffered (cached = True)."""
        db, _ = _make_db()
        cache._db = db
        result = await cache.put("p1", 1.0, 2.0, _now())

        assert result is True
        assert "p1" in cache._buffer


    @pytest.mark.asyncio
    async def test_put_keeps_only_latest_position(self, cache):
        db, _ = _make_db()
        cache._db = db
        await cache.put("p1", 1.0, 1.0, _now())
        await cache.put("p1", 9.0, 9.0, _now())

        assert cache._buffer["p1"].x == 9.0
        assert cache._buffer["p1"].y == 9.0


    @pytest.mark.asyncio
    async def test_pending_count_increments(self, cache):
        db, _ = _make_db()
        cache._db = db
        await cache.put("p1", 0.0, 0.0, _now())
        await cache.put("p1", 1.0, 1.0, _now())

        assert cache._buffer["p1"].pending_count == 2


    @pytest.mark.asyncio
    async def test_multiple_players_buffered_independently(self, cache):
        db, _ = _make_db()
        cache._db = db
        await cache.put("p1", 1.0, 1.0, _now())
        await cache.put("p2", 2.0, 2.0, _now())

        assert "p1" in cache._buffer
        assert "p2" in cache._buffer


    @pytest.mark.asyncio
    async def test_force_flush_at_max_pending_returns_false(self, cache):
        db, col = _make_db()
        cache._db = db

        from app.core.config import get_settings
        # fill up to max_pending - 1 so the next write triggers the flush.
        for i in range(get_settings().position_cache_max_pending - 1):
            await cache.put("p1", float(i), float(i), _now())

        result = await cache.put("p1", 5.0, 5.0, _now())

        assert result is False  # flushed immediately
        col.bulk_write.assert_awaited_once()


    @pytest.mark.asyncio
    async def test_flush_all_drains_buffer(self, cache):
        """flush_all should write all buffered users and leave the buffer empty."""
        db, col = _make_db()
        cache._db = db

        await cache.put("p2", 2.0, 2.0, _now())

        from app.core.config import get_settings
        for _ in range(get_settings().position_cache_max_pending):
            await cache.put("p1", 1.0, 1.0, _now())

        assert len(cache._buffer) == 0
        ops = col.bulk_write.call_args[0][0]
        flushed_ids = {op._doc["user_id"] for op in ops}
        assert "p1" in flushed_ids
        assert "p2" in flushed_ids


class TestPositionWriteCache_FlushAll:

    @pytest.mark.asyncio
    async def test_bulk_write_called_with_all_buffered_entries(self, cache):
        db, collection = _make_db()
        cache._db = db
        await cache.put("p1", 1.0, 1.0, _now())
        await cache.put("p2", 2.0, 2.0, _now())
        await cache.flush_all()

        collection.bulk_write.assert_called_once()
        ops = collection.bulk_write.call_args[0][0]
        user_ids = {op._doc["user_id"] for op in ops}

        assert user_ids == {"p1", "p2"}


    @pytest.mark.asyncio
    async def test_buffer_empty_after_flush(self, cache):
        db, _ = _make_db()
        cache._db = db
        await cache.put("p1", 1.0, 1.0, _now())
        await cache.flush_all()
        assert cache._buffer == {}


    @pytest.mark.asyncio
    async def test_flush_on_empty_buffer_does_not_call_bulk_write(self, cache):
        db, col = _make_db()
        cache._db = db
        await cache.flush_all()
        col.bulk_write.assert_not_awaited()


    @pytest.mark.asyncio
    async def test_flush_targets_positions_collection(self, cache):
        db, _ = _make_db()
        cache._db = db
        await cache.put("p1", 1.0, 1.0, _now())
        await cache.flush_all()
        db.__getitem__.assert_called_with(get_settings().fast_position_collection_name)


    @pytest.mark.asyncio
    async def test_inserted_document_shape(self, cache):
        db, col = _make_db()
        cache._db = db
        ts = _now()
        await cache.put("p1", 3.0, 4.0, ts)
        await cache.flush_all()

        ops = col.bulk_write.call_args[0][0]
        assert len(ops) == 1
        doc = ops[0]._doc
        assert doc["user_id"] == "p1"
        assert doc["x"] == 3.0
        assert doc["y"] == 4.0
        assert doc["timestamp"] == ts


    @pytest.mark.asyncio
    async def test_noop_when_db_not_set(self, cache):
        """flush_all with no DB handle must not raise."""
        cache._db = None
        cache._buffer["p1"] = _BufferedPosition("p1", 1.0, 1.0, _now())
        await cache.flush_all()  # should be a no-op


class TestPositionWriteCache_Failure:

    @pytest.mark.asyncio
    async def test_failed_flush_rebuffers_entry(self, cache):
        """If a DB write fails, the entry should be put back in the buffer."""
        db, _ = _make_db(bulk_write_side_effect=Exception("DB error"))
        cache._db = db

        await cache.put("p1", 1.0, 1.0, _now())
        await cache.put("p2", 2.0, 2.0, _now())

        with pytest.raises(Exception, match="DB error"):
            await cache.flush_all()

        # entry must be re-buffered so ti can be retried
        assert "p1" in cache._buffer
        assert "p2" in cache._buffer
