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


def _make_db(position_docs=None):
    """Builds a miniaml mock AsyncDatabase for testing"""

    db = MagicMock()

    position_docs = position_docs or {}

    def _get_collection(name):
        uid = name.removeprefix("positions_")
        pos_col = MagicMock()
        pos_col.find_one = AsyncMock(return_value=position_docs.get(uid))

        return pos_col

    db.__getitem__ = MagicMock(side_effect=_get_collection)
    return db


@pytest.fixture
def cache():
    """Fresh cache instance per test to avoid a shared singleton state"""
    return PositionReadCache()


class TestPositionReadCache_GetMany:

    def test_returns_matching_records(self, cache):
        cache._snapshot = {
            "p1": _record("p1"),
            "p2": _record("p2"),
            "p3": _record("p3"),
        }
        result = cache.get_many(["p1", "p3"])

        assert set(result.keys()) == {"p1", "p3"}


    def test_omits_unknown_ids(self, cache):
        """user_ids not in the snapshot are silently excluded, not an error."""
        cache._snapshot = {"p1": _record("p1")}
        result = cache.get_many(["p1", "unknown"])

        assert set(result.keys()) == {"p1"}


    def test_returns_empty_dict_when_snapshot_empty(self, cache):
        result = cache.get_many(["p1", "p2"])

        assert result == {}


    def test_returns_empty_dict_for_empty_request(self, cache):
        cache._snapshot = {"p1": _record("p1")}

        assert cache.get_many([]) == {}


    def test_does_not_mutate_snapshot(self, cache):
        """Callers modifying the returned dict must not corrupt the snapshot."""
        rec = _record("p1")
        cache._snapshot = {"p1": rec}
        result = cache.get_many(["p1"])
        result["p2"] = _record("p2")

        assert "p2" not in cache._snapshot


    def test_returns_correct_record_values(self, cache):
        rec = _record("p1", x=7.0, y=8.0)
        cache._snapshot = {"p1": rec}
        result = cache.get_many(["p1"])

        assert result["p1"].x == 7.0
        assert result["p1"].y == 8.0


class TestPositionReadCache_FetchFromDB:

    @pytest.mark.asyncio
    async def test_returns_record_when_document_exists(self, cache):
        doc = {
            "user_id": "p1", "x": 3.0, "y": 4.0, "timestamp": datetime.now(tz=timezone.utc)
        }
        db = _make_db(position_docs={"p1": doc})
        cache._db = db
        result = await cache._fetch_from_db("p1")

        assert result is not None
        assert result.user_id == "p1"
        assert result.x == 3.0


    @pytest.mark.asyncio
    async def test_returns_none_when_no_document(self, cache):
        db = _make_db({"p1": None})
        cache._db = db
        result = await cache._fetch_from_db("p1")

        assert result is None


    @pytest.mark.asyncio
    async def test_queries_correct_collection(self, cache):
        """Must look in positions_{user_id}, not some other collection."""
        doc = {
            "user_id": "p1", "x": 1.0, "y": 1.0, "timestamp": datetime.now(tz=timezone.utc)
        }
        db = _make_db(position_docs={"rick-and-morty": doc})
        cache._db = db
        await cache._fetch_from_db("rich-and-morty")

        db.__getitem__.assert_called_once_with("positions_rich-and-morty")












