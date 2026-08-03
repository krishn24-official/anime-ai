from app.repositories.actors_repository import (
    get_all_actors,
    get_actor_by_id,
    search_actors,
    get_birthdays_by_date_range
)

async def fetch_all_actors(include_deleted: bool = False, search: str = None, limit: int = 50, skip: int = 0):
    return await get_all_actors(include_deleted, search, limit, skip)

async def fetch_actor(actor_id: str):
    return await get_actor_by_id(actor_id)

async def search_actor(query: str):
    if not query or len(query) < 2:
        return []
    return await search_actors(query)

async def fetch_birthdays_by_date_range(start_date: str, end_date: str):
    return await get_birthdays_by_date_range(start_date, end_date)

async def fetch_actor_filmography(actor: dict) -> list[dict]:
    from app.db.mongo import get_db
    db = get_db()
    search_query = {
        "$or": [
            {"cast.actor_id": actor["_id"]},
            {"director.actor_id": actor["_id"]},
            {"creators.actor_id": actor["_id"]},
            {"actors": actor["name"]},
            {"director": actor["name"]},
            {"crew": actor["name"]},
            {"producers": actor["name"]}
        ],
        "is_deleted": False
    }
    movies = await db["movies"].find(search_query).to_list(None)
    tv = await db["tv_series"].find(search_query).to_list(None)
    
    filmography = []
    
    for m in movies:
        filmography.append({
            "id": m["_id"],
            "title": m.get("title"),
            "year": m.get("year"),
            "content_type": "movie",
            "poster": m.get("images", {}).get("poster")
        })
        
    for t in tv:
        filmography.append({
            "id": t["_id"],
            "title": t.get("title"),
            "year": t.get("year"),
            "content_type": "tv_series",
            "poster": t.get("images", {}).get("poster")
        })
    
    def safe_year(x):
        y = x.get("year")
        if not y:
            return 0
        try:
            return int(y)
        except (ValueError, TypeError):
            return 0

    filmography.sort(key=safe_year, reverse=True)
    return filmography
