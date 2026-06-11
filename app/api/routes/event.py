from fastapi import APIRouter

from app.services.event_service import (
    fetch_today_events
)

router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


@router.get("/today")
async def get_events_today():

    return await (
        fetch_today_events()
    )