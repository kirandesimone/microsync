"""REST endpoints for fast positions."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, status, HTTPException

from app.schemas.position import (
    AllPositionsResponse,
    PositionPublishRequest,
    PositionPublishResponse
)
from app.services.position_read_cache import position_read_cache
from app.services.position_write_cache import position_write_cache

log = logging.getLogger(__name__)
router = APIRouter(prefix="/fast-positions", tags=["fast-positions"])


@router.post(
    "/publish",
    response_model=PositionPublishResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a position for a player"
)
async def publish_position(
    payload: PositionPublishRequest
) -> PositionPublishResponse:
    now = datetime.now(tz=timezone.utc)
    try:
        cached = await position_write_cache.put(
            user_id=payload.user_id,
            x=payload.x,
            y=payload.y,
            timestamp=now
        )
    except Exception as e:
        log.exception(f"Write failed for user={payload.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to write position to cache"
        ) from e

    return PositionPublishResponse(
        user_id=payload.user_id,
        x=payload.x,
        y=payload.y,
        timestamp=now,
        cached=cached
    )


@router.get(
    "/",
    response_model=AllPositionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all known player positions",
    description=(
        "Returns the latest cached position for every player the service knows about."
    )
)
async def get_all_positions() -> AllPositionsResponse:
    positions = list(position_read_cache.get_many().values())
    return AllPositionsResponse(positions=positions, count=len(positions))
