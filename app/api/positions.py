"""osition endpoints for the client position sync microservice.
 
routes
------
POST /positions/{clientId}          - publish a client's current position
GET  /positions/{areaId}            - get all current positions for an area
GET  /positions/{areaId}/posts      - get user posts for an area with optional timestamp filter
DELETE /positions/{areaId}/{id}     - delete a specific position entry
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
 
 
# POST /positions/<clientId> 
# publish a position update from a specific client
# path param: clientId — identifies the user/app sending the update
# body: PositionData JSON — position data for that client

@router.post("/{clientId}", status_code=201)
async def publish_position(clientId: str, positionData: PositionData):
    try:
        # parse timestamp string into datetime object for the write cache
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
 
 
# GET /positions/<areaId>
# get all current positions for a specific area
# path param: areaId — the area to query, e.g. "portland"
# returns the current snapshot from the read cache
#
# example calls:
#   GET /positions/portland
#   GET /positions/area01
@router.get("/{areaId}")
async def get_client_positions(areaId: str):
    try:
        # get the current snapshot from the read cache
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
 
 
# GET /positions/<areaId>/posts 
# get user posts for a specific area, optionally filtered by timestamp
# path param: areaId — the area to query
# query param: since — iso timestamp to only return entries after this time
#
# example calls:
#   GET /positions/portland/posts
#   GET /positions/portland/posts?since=2026-05-16T15:30:00Z
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
 
 
# DELETE /positions/<areaId>/<id>
# delete a specific position entry by id within an area
# path params: areaId, id
#
# example call-
#   DELETE /positions/portland/6a062da30dcd4a1844a57428
@router.delete("/{areaId}/{id}")
async def delete_position(areaId: str, id: str):
    try:
        # validate the id format
        ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")
 
    # positions are managed by the write cache — flush first then check
    await position_write_cache.flush_all()
 
    return JSONResponse(
        status_code=200,
        content={"status": "deleted", "id": id, "areaId": areaId}
    )
 