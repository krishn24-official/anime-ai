from app.container import content_catalog
from app.domain.shared.content import ContentRef
from app.repositories.event_repository import get_today_events, get_events_by_date_range


async def _with_parent_info(events: list[dict]) -> list[dict]:
    """Add the parent anime/manga (title, poster) to each event.

    Events only store anime_id / manga_id; clients need a title and an image to
    show them. Adds: parent_type, parent_id, parent_title, poster_image.
    """
    refs = {}
    for event in events:
        if event.get("anime_id"):
            refs[id(event)] = ContentRef("anime", event["anime_id"])
        elif event.get("manga_id"):
            refs[id(event)] = ContentRef("manga", event["manga_id"])

    summaries = await content_catalog().get_summaries(list(set(refs.values())))

    for event in events:
        ref = refs.get(id(event))
        summary = summaries.get(ref) if ref else None
        event["parent_type"] = ref.content_type if ref else None
        event["parent_id"] = ref.content_id if ref else None
        event["parent_title"] = summary.title if summary else None
        event["poster_image"] = summary.poster_image if summary else None
    return events


async def fetch_today_events():
    return await _with_parent_info(await get_today_events())


async def fetch_events_by_date_range(start_date: str, end_date: str):
    return await _with_parent_info(await get_events_by_date_range(start_date, end_date))
