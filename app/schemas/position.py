"""Request / response shapes for position endpoints"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PositionRecord(BaseModel):
    """Shape of a position document stored in MongoDB"""

    model_config = ConfigDict(extra="allow")  # so the new int params pass through

    user_id: str
    x: float
    y: float
    timestamp: datetime

