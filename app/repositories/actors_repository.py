from datetime import datetime, timezone
import re
from app.db.mongo import get_db
from app.utils.search_utils import build_fuzzy_search_regex

async def get_all_actors(include_deleted: bool = False, search: str = None, limit: int = 50, skip: int = 0):
    db = get_db()
    query = {} if include_deleted else {"is_deleted": False}
    
    if search:
        fuzzy_pattern = build_fuzzy_search_regex(search)
        search_regex = re.compile(fuzzy_pattern, re.IGNORECASE)
        query["name"] = search_regex
        
    cursor = db["actors"].find(query).sort("name", 1).skip(skip).limit(limit)
    items = await cursor.to_list(None)
    total = await db["actors"].count_documents(query)
    
    return {"items": items, "total": total}

async def get_actor_by_id(actor_identifier: str):
    db = get_db()
    # First try by _id
    actor = await db["actors"].find_one({"_id": actor_identifier, "is_deleted": False})
    if actor:
        return actor
    # Fallback to exact name match
    return await db["actors"].find_one({"name": actor_identifier, "is_deleted": False})

async def search_actors(query: str, limit: int = 20):
    db = get_db()
    cursor = await db["actors"].aggregate([
        {
            "$match": {
                "name": {"$regex": query, "$options": "i"},
                "is_deleted": False
            }
        },
        {
            "$addFields": {
                "name_length": {"$strLenCP": {"$ifNull": ["$name", ""]}}
            }
        },
        {
            "$sort": {"name_length": 1}
        },
        {
            "$limit": limit
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "images.profile": 1
            }
        }
    ])
    return await cursor.to_list(None)

async def create_actor(doc: dict):
    db = get_db()
    await db["actors"].insert_one(doc)
    return doc["_id"]

async def update_actor(actor_id: str, updates: dict):
    db = get_db()
    if not updates:
        return True
    result = await db["actors"].update_one(
        {"_id": actor_id},
        {"$set": updates}
    )
    return result.modified_count > 0

async def soft_delete_actor(actor_id: str):
    db = get_db()
    result = await db["actors"].update_one(
        {"_id": actor_id},
        {
            "$set": {
                "is_deleted": True,
                "deleted_at": datetime.now(timezone.utc)
            }
        }
    )
    return result.modified_count > 0

async def get_birthdays_by_date_range(start_date: str, end_date: str):
    from datetime import timedelta
    db = get_db()
    
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return []
        
    if end_dt < start_dt:
        return []
        
    days = (end_dt - start_dt).days
    if days > 366:
        days = 366
        
    date_criteria = []
    for i in range(days + 1):
        dt = start_dt + timedelta(days=i)
        # Actor birthdate is stored as YYYY-MM-DD from TMDB
        date_criteria.append({"birthdate": {"$regex": f"-{dt.month:02d}-{dt.day:02d}$"}})
        
        # Manually updated actors might have "Month D, YYYY" or "Month DD, YYYY"
        month_name = dt.strftime("%B")
        date_criteria.append({"birthdate": {"$regex": f"^{month_name} {dt.day},"}})
        
    if not date_criteria:
        return []
        
    actors = await db["actors"].find(
        {
            "$or": date_criteria,
            "is_deleted": False
        },
        {
            "_id": 1,
            "name": 1,
            "images.profile": 1,
            "birthdate": 1
        }
    ).to_list(None)

    # Format like characters (birth_month, birth_day) for compatibility with frontend schedule
    for actor in actors:
        actor["entity_type"] = "actor"
        bd = actor.get("birthdate")
        if bd:
            if "-" in bd:
                parts = bd.split("-")
                if len(parts) == 3:
                    actor["birth_month"] = int(parts[1])
                    actor["birth_day"] = int(parts[2])
            else:
                # Fallback for "Month D, YYYY"
                try:
                    # Strip out comma if present
                    clean_bd = bd.replace(",", "")
                    parts = clean_bd.split(" ")
                    if len(parts) >= 2:
                        from datetime import datetime
                        dt_obj = datetime.strptime(parts[0], "%B")
                        actor["birth_month"] = dt_obj.month
                        actor["birth_day"] = int(parts[1])
                except (ValueError, IndexError):
                    pass

    return actors

import difflib
import re
import time
from app.db.mongo import get_db

_actor_cache: dict = {}
CACHE_TTL = 300

_actor_name_list: list[str] = []
_actor_word_map: dict[str, list[str]] = {}
_actor_name_cache_loaded: bool = False

async def _load_actor_name_cache() -> None:
    global _actor_name_list, _actor_word_map, _actor_name_cache_loaded
    if _actor_name_cache_loaded:
        return

    db = get_db()
    docs = await db["actors"].find({"is_deleted": False}, {"name": 1}).to_list(None)
    names = [d["name"] for d in docs if d.get("name")]

    word_map: dict[str, list[str]] = {}
    for name in names:
        for word in name.lower().split():
            if len(word) >= 3:
                word_map.setdefault(word, []).append(name)

    _actor_name_list = names
    _actor_word_map = word_map
    _actor_name_cache_loaded = True

async def find_actor(name: str):
    name_clean = name.strip()
    cache_key = name_clean.lower()

    cached = _actor_cache.get(cache_key)
    if cached:
        doc, ts = cached
        if time.time() - ts < CACHE_TTL:
            return doc

    db = get_db()

    result = await db["actors"].find_one(
        {"name": {"$regex": f"^{re.escape(name_clean)}$", "$options": "i"}, "is_deleted": False}
    )
    if result:
        _actor_cache[cache_key] = (result, time.time())
        return result

    result = await db["actors"].find_one(
        {"name": {"$regex": f"^{re.escape(name_clean)}", "$options": "i"}, "is_deleted": False}
    )
    if result:
        _actor_cache[cache_key] = (result, time.time())
        return result

    result = await db["actors"].find_one(
        {"name": {"$regex": re.escape(name_clean), "$options": "i"}, "is_deleted": False}
    )
    if result:
        _actor_cache[cache_key] = (result, time.time())
    return result

async def find_actor_candidates(name: str, limit: int = 5) -> list:
    name_clean = name.strip()
    db = get_db()

    exact = await db["actors"].find(
        {"name": {"$regex": f"^{re.escape(name_clean)}$", "$options": "i"}, "is_deleted": False}
    ).to_list(None)
    if exact:
        return exact[:limit]

    starts = await db["actors"].find(
        {"name": {"$regex": f"^{re.escape(name_clean)}", "$options": "i"}, "is_deleted": False}
    ).limit(limit).to_list(None)
    if starts:
        return starts

    contains = await db["actors"].find(
        {"name": {"$regex": re.escape(name_clean), "$options": "i"}, "is_deleted": False}
    ).limit(limit).to_list(None)
    if contains:
        return contains

    await _load_actor_name_cache()
    if not _actor_word_map:
        return []

    matched_full_names: set[str] = set()
    all_index_words = list(_actor_word_map.keys())

    clean_for_fuzzy = re.sub(r"['’]s\b", "", name_clean.lower())
    clean_for_fuzzy = re.sub(r"[^\w\s]", "", clean_for_fuzzy)

    stop_words = {"the", "and", "for", "with", "about", "actor", "who", "what", "is", "tell", "me", "show"}

    for query_word in clean_for_fuzzy.split():
        if len(query_word) < 3 or query_word in stop_words:
            continue
        close_words = difflib.get_close_matches(
            query_word, all_index_words, n=3, cutoff=0.70
        )
        for cw in close_words:
            for full_name in _actor_word_map.get(cw, []):
                matched_full_names.add(full_name)

    if not matched_full_names:
        return []

    results = []
    for full_name in list(matched_full_names)[:limit]:
        char = await db["actors"].find_one({"name": full_name, "is_deleted": False})
        if char:
            results.append(char)
    return results
