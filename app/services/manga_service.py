from app.repositories.manga_repository import (
    get_all_manga,
    get_manga_by_id,
)
from app.services.search_listing import ranked_documents


def _serialize(item: dict) -> dict:
    item = dict(item)
    item["id"] = str(item.pop("_id"))
    return item


async def fetch_all_manga(page: int = 1, limit: int = 50, search: str = None):
    if search:  # ranked by relevance, same as the global search bar
        items, total = await ranked_documents("manga", search, limit, (page - 1) * limit)
    else:
        items, total = await get_all_manga(page, limit)

    return {
        "items": [_serialize(m) for m in items],
        "total": total,
        "page": page,
        "limit": limit,
    }


async def fetch_manga(manga_id: str):

    return await get_manga_by_id(manga_id)


async def fetch_manga_search(query: str):

    items, _ = await ranked_documents("manga", query, limit=20)
    return items


async def fetch_manga_summary(manga_id: str):

    manga = await get_manga_by_id(manga_id)

    if not manga:
        return None

    return {
        "_id": manga["_id"],
        "name": manga.get("name"),
        "author": manga.get("author"),
        "status": manga.get("status"),
        "total_chapters": manga.get("total_chapters"),
        "cover_image": manga.get("cover_image"),
    }


async def fetch_manga_details(manga_id: str):

    manga = await get_manga_by_id(manga_id)

    if not manga:
        return None

    return {"manga": manga}
