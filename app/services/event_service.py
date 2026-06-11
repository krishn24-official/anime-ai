from app.repositories.event_repository import (
    get_today_events
)


async def fetch_today_events():

    return await (
        get_today_events()
    )