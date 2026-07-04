from app.repositories.event_repository import (
    get_today_events,
    get_events_by_date_range
)


async def fetch_today_events():

    return await (
        get_today_events()
    )


async def fetch_events_by_date_range(start_date: str, end_date: str):
    return await get_events_by_date_range(start_date, end_date)