"""Tests for the position read-cache"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.position import PositionRecord
from app.services.position_read_cache import PositionReadCache


# Helpers

def _record(user_id: str, x: float = 1.0, y: float = 2.0) -> PositionRecord:
    return PositionRecord(user_id=user_id, x=x, y=y, timestamp=datetime.now(tz=timezone.utc))


def _make_db(agg_results=None, agg_side_effect=None):
    """Builds a miniaml mock AsyncDatabase for testing"""

    collection = MagicMock()

    async def _fake_cursor():
        for item in (agg_results or []):
            yield item

    if agg_side_effect:
        collection.aggregate = MagicMock(side_effect=agg_side_effect)
    else:
        collection.aggregate = MagicMock(return_value=_fake_cursor())

    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=collection)
    return db, collection


def _agg_row(user_id: str, x: float = 1.0, y: float = 2.0) -> dict:
    """Build a pipeline result row as MongoDB would return it."""
    return {
        "_id": user_id,
        "doc": {
            "_id": "mongo_object_id",
            "user_id": user_id,
            "x": x,
            "y": y,
            "timestamp": datetime.now(tz=timezone.utc),
        },
    }


@pytest.fixture
def cache():
    """Fresh cache instance per test to avoid a shared singleton state"""
    return PositionReadCache()


class TestPositionReadCache_GetMany:

    def test_returns_empty_dict_when_snapshot_empty(self, cache):
        assert cache.get_many() == {}

    def test_returns_all_players_in_snapshot(self, cache):
        cache._snapshot = {"p1": _record("p1"), "p2": _record("p2")}
        result = cache.get_many()

        assert set(result.keys()) == {"p1", "p2"}

    def test_returns_copy_not_reference(self, cache):
        """Mutating the returned dict must not corrupt the snapshot."""
        cache._snapshot = {"p1": _record("p1")}
        result = cache.get_many()
        result["p2"] = _record("p2")

        assert "p2" not in cache._snapshot

    def test_returns_correct_values(self, cache):
        cache._snapshot = {"p1": _record("p1", x=5.0, y=6.0)}
        result = cache.get_many()

        assert result["p1"].x == 5.0
        assert result["p1"].y == 6.0



class TestRefresh:

    @pytest.mark.asyncio
    async def test_snapshot_populated_from_aggregation(self, cache):
        db, _ = _make_db(agg_results=[_agg_row("p1"), _agg_row("p2")])
        cache._db = db
        await cache._refresh()

        assert set(cache._snapshot.keys()) == {"p1", "p2"}


    @pytest.mark.asyncio
    async def test_snapshot_cleared_when_no_results(self, cache):
        cache._snapshot = {"p1": _record("p1")}
        db, _ = _make_db(agg_results=[])
        cache._db = db
        await cache._refresh()

        assert cache._snapshot == {}


    @pytest.mark.asyncio
    async def test_mongo_id_stripped_from_records(self, cache):
        """_id from the doc subdocument should not leak into PositionRecord."""
        db, _ = _make_db(agg_results=[_agg_row("p1")])
        cache._db = db
        await cache._refresh()
        record = cache._snapshot["p1"]

        assert not hasattr(record, "_id")


    @pytest.mark.asyncio
    async def test_correct_values_stored_in_snapshot(self, cache):
        db, _ = _make_db(agg_results=[_agg_row("p1", x=7.0, y=8.0)])
        cache._db = db
        await cache._refresh()

        assert cache._snapshot["p1"].x == 7.0
        assert cache._snapshot["p1"].y == 8.0


    @pytest.mark.asyncio
    async def test_snapshot_replaced_not_merged(self, cache):
        """Players absent from the new aggregation result must not persist."""
        cache._snapshot = {"old_player": _record("old_player")}
        db, _ = _make_db(agg_results=[_agg_row("p1")])
        cache._db = db
        await cache._refresh()

        assert "old_player" not in cache._snapshot
        assert "p1" in cache._snapshot


    @pytest.mark.asyncio
    async def test_stale_snapshot_retained_on_db_failure(self, cache):
        """If the aggregation raises, the existing snapshot must be preserved."""
        stale = _record("p1", x=9.0)
        cache._snapshot = {"p1": stale}
        db, _ = _make_db(agg_side_effect=Exception("DB timeout"))
        cache._db = db
        await cache._refresh()  # must not raise

        assert cache._snapshot["p1"].x == 9.0


    @pytest.mark.asyncio
    async def test_noop_when_db_not_set(self, cache):
        cache._db = None
        await cache._refresh()
        assert cache._snapshot == {}


    @pytest.mark.asyncio
    async def test_queries_single_positions_collection(self, cache):
        """Aggregation must target POSITIONS_COLLECTION, not per-player collection."""
        from app.core.config import get_settings

        db, _ = _make_db(agg_results=[])
        cache._db = db
        await cache._refresh()
        
        db.__getitem__.assert_called_with(get_settings().position_collection_name)


    @pytest.mark.asyncio
    async def test_single_aggregation_call_regardless_of_player_count(self, cache):
        """Exactly one aggregate() call per refresh — not one per player."""
        rows = [_agg_row(f"p{i}") for i in range(5)]
        db, collection = _make_db(agg_results=rows)
        cache._db = db
        await cache._refresh()
        
        collection.aggregate.assert_called_once()


