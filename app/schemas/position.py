"""Request / response shapes for position endpoints"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PositionPublishRequest(BaseModel):
    """Payload sent by a client to publish a position"""

    user_id: str = Field(..., min_length=1, max_length=128)
    x: float | int
    y: float | int


class PositionPublishResponse(BaseModel):
    user_id: str
    x: float | int
    y: float | int
    timestamp: datetime
    cached: bool


class PositionRecord(BaseModel):
    """Shape of a position document stored in MongoDB"""

    model_config = ConfigDict(extra="allow")  # so the new int params pass through

    user_id: str
    x: float
    y: float
    timestamp: datetime


class AllPositionsResponse(BaseModel):
    """All currently known player positions"""
    positions: list[PositionRecord]
    count: int
