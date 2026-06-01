"""
Position endpoints for the client position sync microservice.
"""
 
from datetime import datetime, timezone
from typing import Optional
 
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
 
from app.services.position_read_cache import position_read_cache
from app.services.position_write_cache import position_write_cache
 
router = APIRouter(prefix="/positions", tags=["positions"])
 
 
class PositionData(BaseModel):
    """
    shape of a position update from any client app.
 
    
    """
    x: float
    y: float
    timestamp: str
    areaId: str
    public: bool = True
 
    model_config = {"extra": "allow"}
 
 
@router.post("/{clientId}", status_code=201)
async def publish_position(clientId: str, positionData: PositionData):
    try:
        try:
            ts = datetime.fromisoformat(
                positionData.timestamp.replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timestamp format: {positionData.timestamp}"
            )
 
        # buffer the position update via the write cache
        buffered = await position_write_cache.put(
            user_id=clientId,
            x=positionData.x,
            y=positionData.y,
            timestamp=ts
        )
 
        return JSONResponse(
            status_code=201,
            content={
                "status": "created",
                "clientId": clientId,
                "buffered": buffered,
                "areaId": positionData.areaId
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")
 
 
@router.get("/{areaId}")
async def get_client_positions(areaId: str):
    try:
        snapshot = position_read_cache.get_many()
 
        # filter by areaId
        entries = [
            {
                "user_id": record.user_id,
                "x": record.x,
                "y": record.y,
                "timestamp": record.timestamp.isoformat(),
                **{k: v for k, v in record.model_extra.items()}
            }
            for record in snapshot.values()
            if record.model_extra.get("areaId") == areaId
        ]
 
        return JSONResponse(status_code=200, content=entries)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.get("/{areaId}/posts")
async def get_user_posts(
    areaId: str,
    since: Optional[str] = Query(default=None)
):
    try:
        snapshot = position_read_cache.get_many()
 
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid since timestamp format: {since}"
                )
 
        entries = []
        for record in snapshot.values():
            if record.model_extra.get("areaId") != areaId:
                continue
            if since_dt and record.timestamp <= since_dt:
                continue
            entries.append({
                "user_id": record.user_id,
                "x": record.x,
                "y": record.y,
                "timestamp": record.timestamp.isoformat(),
                **{k: v for k, v in record.model_extra.items()}
            })
 
        return JSONResponse(status_code=200, content=entries)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.delete("/{areaId}/{id}")
async def delete_position(areaId: str, id: str):
    try:
        ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")
 
    await position_write_cache.flush_all()
 
    return JSONResponse(
        status_code=200,
        content={"status": "deleted", "id": id, "areaId": areaId}
    )
 
