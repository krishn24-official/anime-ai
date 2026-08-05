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

async def fetch_actor_filmography(actor: dict) -> dict[str, list[dict]]:
    from app.db.mongo import get_db
    db = get_db()
    search_query = {
        "$or": [
            {"cast.actor_id": actor["_id"]},
            {"director.actor_id": actor["_id"]},
            {"creators.actor_id": actor["_id"]},
            {"writer.actor_id": actor["_id"]},
            {"actors": actor["name"]},
            {"director": actor["name"]},
            {"creators": actor["name"]},
            {"writers": actor["name"]}
        ],
        "is_deleted": False
    }
    movies = await db["movies"].find(search_query).to_list(None)
    tv = await db["tv_series"].find(search_query).to_list(None)
    
    as_actor = []
    as_director = []
    as_writer = []
    
    def add_to_group(item, group_list):
        group_list.append({
            "id": item["_id"],
            "title": item.get("title"),
            "year": item.get("year"),
            "content_type": item.get("content_type"),
            "poster": item.get("images", {}).get("poster")
        })

    actor_id = actor["_id"]
    actor_name = actor.get("name")

    for m in movies:
        is_cast = any(c.get("actor_id") == actor_id for c in (m.get("cast") or []) if isinstance(c, dict)) or (actor_name in (m.get("actors") or []))
        
        dir_val = m.get("director", [])
        is_director = any(d.get("actor_id") == actor_id for d in dir_val if isinstance(d, dict)) or (actor_name in dir_val if isinstance(dir_val, list) and len(dir_val) > 0 and isinstance(dir_val[0], str) else False)
        
        wri_val = m.get("writers", [])
        is_writer = any(w.get("actor_id") == actor_id for w in (m.get("writer") or []) if isinstance(w, dict)) or (actor_name in wri_val if isinstance(wri_val, list) and len(wri_val) > 0 and isinstance(wri_val[0], str) else False)
        
        if is_cast:
            add_to_group(m, as_actor)
        if is_director:
            add_to_group(m, as_director)
        if is_writer:
            add_to_group(m, as_writer)
            
    for t in tv:
        is_cast = any(c.get("actor_id") == actor_id for c in (t.get("cast") or []) if isinstance(c, dict)) or (actor_name in (t.get("actors") or []))
        
        cre_val = t.get("creators", [])
        is_director = any(d.get("actor_id") == actor_id for d in cre_val if isinstance(d, dict)) or (actor_name in cre_val if isinstance(cre_val, list) and len(cre_val) > 0 and isinstance(cre_val[0], str) else False)
        
        wri_val = t.get("writers", [])
        is_writer = any(w.get("actor_id") == actor_id for w in (t.get("writer") or []) if isinstance(w, dict)) or (actor_name in wri_val if isinstance(wri_val, list) and len(wri_val) > 0 and isinstance(wri_val[0], str) else False)
        
        if is_cast:
            add_to_group(t, as_actor)
        if is_director:
            add_to_group(t, as_director)
        if is_writer:
            add_to_group(t, as_writer)
    
    def safe_year(x):
        y = x.get("year")
        if not y:
            return 0
        try:
            return int(y)
        except (ValueError, TypeError):
            return 0

    as_actor.sort(key=safe_year, reverse=True)
    as_director.sort(key=safe_year, reverse=True)
    as_writer.sort(key=safe_year, reverse=True)
    
    result = {}
    if as_actor:
        result["as_actor"] = as_actor
    if as_director:
        result["as_director"] = as_director
    if as_writer:
        result["as_writer"] = as_writer
        
    return result
