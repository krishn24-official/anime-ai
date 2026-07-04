from fastapi import APIRouter, Query

from app.services.event_service import (
    fetch_today_events,
    fetch_events_by_date_range
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


@router.get("/range")
async def get_events_range(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format")
):
    return await fetch_events_by_date_range(start_date, end_date)