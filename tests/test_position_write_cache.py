"""Tests for the position write-cache"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.position_write_cache import PositionWriteCache


@pytest.fixture
def cache():
    """Fresh cache instance per test to avoid a shared singleton state"""
    return PositionWriteCache()


@pytest.fixture
def mock_db():
    db = MagicMock()
    collection = MagicMock()
    collection.insert_one = AsyncMock(return_value=None)
    db.__getitem__ = MagicMock(return_value=collection)

    return db, collection


class TestPositionWriteCache:

    @pytest.mark.asyncio
    async def test_put_returns_true_when_buffered(self, cache, mock_db):
        """First write for a user should be buffered (cached = True)."""
        db, _ = mock_db
        cache._db = db
        result = await cache.put("player1", 1.0, 2.0, datetime.now(tz=timezone.utc))

        assert result is True


    @pytest.mark.asyncio
    async def test_put_flushes_immediately_at_max_pending(self, cache, mock_db):
        """After max_pending writes, the cache should flush immediately and return False"""
        db, col = mock_db
        cache._db = db

        from app.core.config import get_settings
        # fill up to max_pending - 1 so the next write triggers the flush.
        for i in range(get_settings().position_cache_max_pending - 1):
            await cache.put("player1", float(i), float(i), datetime.now(tz=timezone.utc))

        result = await cache.put("player1", 99.0, 99.0, datetime.now(tz=timezone.utc))

        assert result is False  # flushed immediately
        col.insert_one.assert_called_once()


    @pytest.mark.asyncio
    async def test_flush_all_drains_buffer(self, cache, mock_db):
        """flush_all should write all buffered users and leave the buffer empty."""
        db, col = mock_db
        cache._db = db

        await cache.put("a", 1.0, 1.0, datetime.now(tz=timezone.utc))
        await cache.put("b", 2.0, 2.0, datetime.now(tz=timezone.utc))

        await cache.flush_all()

        assert len(cache._buffer) == 0
        assert col.insert_one.call_count == 2


    @pytest.mark.asyncio
    async def test_failed_flush_rebuffers_entry(self, cache, mock_db):
        """If a DB write fails, the entry should be put back in the buffer."""
        db, col = mock_db
        col.insert_one = AsyncMock(side_effect=Exception("DB error"))
        cache._db = db

        await cache.put("player1", 5.0, 5.0, datetime.now(tz=timezone.utc))

        with pytest.raises(Exception):
            await cache.flush_all()

        # entry must be re-buffered so ti can be retried
        assert "player1" in cache._buffer
