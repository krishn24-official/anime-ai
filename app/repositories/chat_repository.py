import re
import time
from app.db.mongo import get_db

_char_cache: dict = {}
CACHE_TTL = 300  # 5 minutes

async def find_character(name: str):
    name_clean = name.strip()
    cache_key = name_clean.lower()

    # At start of find_character — check cache first:
    cached = _char_cache.get(cache_key)
    if cached:
        doc, ts = cached
        if time.time() - ts < CACHE_TTL:
            return doc

    db = get_db()

    # 1. Exact match first (fastest)
    result = await db["characters"].find_one(
        {"name": {"$regex": f"^{re.escape(name_clean)}$", "$options": "i"}}
    )
    if result:
        _char_cache[cache_key] = (result, time.time())
        return result

    # 2. Starts-with match
    result = await db["characters"].find_one(
        {"name": {"$regex": f"^{re.escape(name_clean)}", "$options": "i"}}
    )
    if result:
        _char_cache[cache_key] = (result, time.time())
        return result

    # 3. Contains match (last resort)
    result = await db["characters"].find_one(
        {"name": {"$regex": re.escape(name_clean), "$options": "i"}}
    )
    if result:
        _char_cache[cache_key] = (result, time.time())
    return result