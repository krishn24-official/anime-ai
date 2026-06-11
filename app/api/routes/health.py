from fastapi import APIRouter

from app.services.health_service import (
    fetch_health
)

router = APIRouter(
    tags=["Health"]
)


@router.get(
    "/health"
)
async def health():

    return await (
        fetch_health()
    )