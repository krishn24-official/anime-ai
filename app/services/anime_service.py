from app.repositories.anime_repository import (
    get_all_anime,
    get_anime_by_id,
    get_anime_characters,
    get_character_count,
    get_anime_voice_actors,
)
from app.services.search_listing import ranked_documents


def _serialize(item: dict) -> dict:
    item = dict(item)
    item["id"] = str(item.pop("_id"))
    return item


async def fetch_all_anime(page: int = 1, limit: int = 50, search: str = None):
    if search:  # ranked by relevance, same as the global search bar
        items, total = await ranked_documents("anime", search, limit, (page - 1) * limit)
    else:
        items, total = await get_all_anime(page, limit)

    return {
        "items": [_serialize(m) for m in items],
        "total": total,
        "page": page,
        "limit": limit,
    }


async def fetch_anime(anime_id: str):

    return await get_anime_by_id(anime_id)


async def fetch_anime_search(query: str):

    items, _ = await ranked_documents("anime", query, limit=20)
    return items


async def fetch_anime_characters(anime_id: str):

    return await get_anime_characters(anime_id)


async def fetch_anime_details(anime_id: str):

    anime = await get_anime_by_id(anime_id)

    if not anime:
        return None

    character_count = await get_character_count(anime_id)

    voice_actors = await get_anime_voice_actors(anime_id, limit=10)

    return {
        "anime": anime,
        "character_count": character_count,
        "voice_actors": voice_actors,
    }


async def fetch_anime_summary(anime_id: str):

    anime = await get_anime_by_id(anime_id)

    if not anime:
        return None

    character_count = await get_character_count(anime_id)

    return {
        "_id": anime["_id"],
        "title": anime.get("title"),
        "image": (anime.get("images", {}).get("poster")),
        "type": anime.get("type"),
        "status": anime.get("status"),
        "year": anime.get("year"),
        "season": anime.get("season"),
        "genres": anime.get("genres", []),
        "character_count": character_count,
    }
