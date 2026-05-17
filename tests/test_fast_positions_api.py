from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.database.mongo import get_db
from app.main import create_app
from app.services.position_read_cache import position_read_cache
from app.services.position_write_cache import position_write_cache


def _make_mock_db():
    """Minimal AsyncDatabase mock"""
    col = MagicMock()
    col.insert_one = AsyncMock(return_value=MagicMock())
    col.bulk_write = AsyncMock(return_value=MagicMock())
    col.create_indexes = AsyncMock(return_value=None)

    # find() returns a cursor-like mock
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=[])
    col.find = MagicMock(return_value=cursor)

    async def _empty_agg(*args, **kwargs):
        return
        yield   # pragma: no cover - makes this an async generator

    col.aggregate = MagicMock(return_value=_empty_agg())

    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)
    db.list_collection_names = AsyncMock(return_value=[])
    db.command = AsyncMock(return_value={"ok": 1})
    return db


@pytest.fixture
def client():
    """Build a fresh app with a test lifespan, then wrap it in TestClient."""
    mock_db = _make_mock_db()

    @asynccontextmanager
    async def test_lifespan(_app):
        position_write_cache.start(mock_db)
        position_read_cache.start(mock_db)
        try:
            yield
        finally:
            await position_write_cache.stop()
            await position_read_cache.stop()

    async def override_get_db():
        yield mock_db

    test_app = create_app(lifespan=test_lifespan)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client


class TestFastPositionsApi_Publish:

    def test_status_returns_200(self, client: TestClient) -> None:
        response = client.get("/status")

        assert response.status_code == 200


    def test_valid_publish_returns_201(self, client: TestClient) -> None:
        response = client.post(
            "/positions/publish",
            json={"user_id": "p1", "x": 1.0, "y": 2.0}
        )

        assert response.status_code == 201
        assert response.json()["user_id"] == "p1"
        assert response.json()["x"] == 1.0
        assert response.json()["y"] == 2.0


    def test_missing_user_id_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/positions/publish",
            json={"x": 1.0, "y": 2.0})

        assert response.status_code == 422


    def test_empty_user_id_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/positions/publish",
            json={"user_id": "", "x": 1.0, "y": 2.0},
        )
        assert response.status_code == 422


    def test_response_echoes_coordinates(self, client):
        response = client.post(
            "/positions/publish",
            json={"user_id": "p1", "x": 3.0, "y": 4.0},
        )
        body = response.json()

        assert body["user_id"] == "p1"
        assert body["x"] == 3.0
        assert body["y"] == 4.0


    def test_response_includes_timestamp(self, client):
        response = client.post(
            "/positions/publish",
            json={"user_id": "p1", "x": 0.0, "y": 0.0},
        )
        body = response.json()

        assert "timestamp" in body
        datetime.fromisoformat(body["timestamp"])


    def test_response_includes_cached_flag(self, client):
        response = client.post(
            "/positions/publish",
            json={"user_id": "p1", "x": 0.0, "y": 0.0},
        )
        assert "cached" in response.json()


    def test_nan_coordinate_returns_422(self, client) -> None:
        """NaN coordinates must be rejected before reaching the DB."""
        response = client.post(
            "/positions/publish",
            params={"user_id": "p1", "x": float("inf"), "y": 0.0},
        )
        assert response.status_code == 422


    def test_missing_x_returns_422(self, client):
        """NaN / Infinity coordinates must be rejected before reaching the DB."""
        response = client.post(
            "/positions/publish",
            params={"user_id": "p1", "y": 2.0},
        )
        assert response.status_code == 422


class TestFastPositionsApi_GetPositions:

    def test_returns_200(self, client):
        response = client.get("/positions")
        assert response.status_code == 200


    def test_response_shape(self, client):
        response = client.get("/positions")
        body = response.json()

        assert "positions" in body
        assert "count" in body
        assert isinstance(body["positions"], list)
        assert isinstance(body["count"], int)


    def test_count_matches_positions_length(self, client):
        response = client.get("/positions")
        body = response.json()

        assert body["count"] == len(body["positions"])


class TestFastPositionsApi_TimingMiddleware:

    def test_header_present_on_get(self, client):
        """Every response must have the X-Process-Time-Ms header."""
        response = client.get("/positions")

        assert "x-process-time-ms" in response.headers


    def test_header_present_on_post(self, client):
        """The middleware must fire on POST requests, not just GET."""
        response = client.post(
            "/positions/publish",
            json={"user_id": "p1", "x": 1.0, "y": 2.0}
        )

        assert "x-process-time-ms" in response.headers


    def test_header_is_numeric(self, client):
        """Value must parse as a float number in milliseconds."""
        response = client.get("/positions")
        value = float(response.headers["x-process-time-ms"])

        assert value >= 0.0


    def test_header_present_on_validation_error(self, client):
        """Middleware must run even when 422 is returned."""
        response = client.post(
            "/positions/publish",
            json={"x": 1.0, "y": 2.0}  # missing user_id
        )

        assert response.status_code == 422
        assert "x-process-time-ms" in response.headers
