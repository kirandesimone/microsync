from fastapi import APIRouter

router = APIRouter(tags=["status"])

@router.get("/status", tags=["status"], include_in_schema=False)
async def status() -> dict:
    return {"status": "ok"}
