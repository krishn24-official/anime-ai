import difflib
import re
import time

from app.db.mongo import get_db

# ── TTL cache for resolved character lookups ──────────────────────────────────
_char_cache: dict = {}
CACHE_TTL = 300  # 5 minutes

# ── In-memory character name index (lazy-loaded on first fuzzy request) ───────
# _char_name_list  : all character names from DB (original case)
# _char_word_map   : word (lowercase, ≥3 chars) → [full character names]
# Built once per server process; safe for single-instance deployments.
_char_name_list: list[str] = []
_char_word_map: dict[str, list[str]] = {}
_name_cache_loaded: bool = False


async def _load_name_cache() -> None:
    """Lazily populate the in-memory character name index from MongoDB."""
    global _char_name_list, _char_word_map, _name_cache_loaded
    if _name_cache_loaded:
        return

    db = get_db()
    docs = await db["characters"].find({}, {"name": 1}).to_list(None)
    names = [d["name"] for d in docs if d.get("name")]

    word_map: dict[str, list[str]] = {}
    for name in names:
        for word in name.lower().split():
            if len(word) >= 3:
                word_map.setdefault(word, []).append(name)

    _char_name_list = names
    _char_word_map = word_map
    _name_cache_loaded = True


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


async def find_character_candidates(name: str, limit: int = 5) -> list:
    """
    Returns up to `limit` characters that match `name`.
    Search order:
      1. Exact regex match
      2. Starts-with regex match
      3. Contains regex match
      4. Word-level fuzzy match (≥70% similarity via difflib) — handles
         typos like 'sasue' → 'Sasuke Uchiha', 'nartu' → 'Naruto Uzumaki'.
    Returns full documents so the caller needs no second round-trip.
    """
    name_clean = name.strip()
    db = get_db()

    # 1. Exact match
    exact = await db["characters"].find(
        {"name": {"$regex": f"^{re.escape(name_clean)}$", "$options": "i"}}
    ).to_list(None)
    if exact:
        return exact[:limit]

    # 2. Starts-with match
    starts = await db["characters"].find(
        {"name": {"$regex": f"^{re.escape(name_clean)}", "$options": "i"}}
    ).limit(limit).to_list(None)
    if starts:
        return starts

    # 3. Contains match
    contains = await db["characters"].find(
        {"name": {"$regex": re.escape(name_clean), "$options": "i"}}
    ).limit(limit).to_list(None)
    if contains:
        return contains

    # 4. Fuzzy word-level match — fire only when all regex passes fail.
    #    Splits the query into individual words and fuzzy-matches each word
    #    against the pre-built word index of all character names.
    await _load_name_cache()
    if not _char_word_map:
        return []

    matched_full_names: set[str] = set()
    all_index_words = list(_char_word_map.keys())

    # Strip possessives and punctuation so words like "suke's" become "suke"
    # This prevents the "'s" from lowering the difflib ratio below 0.70!
    clean_for_fuzzy = re.sub(r"['’]s\b", "", name_clean.lower())
    clean_for_fuzzy = re.sub(r"[^\w\s]", "", clean_for_fuzzy)

    for query_word in clean_for_fuzzy.split():
        if len(query_word) < 3:
            continue
        close_words = difflib.get_close_matches(
            query_word, all_index_words, n=3, cutoff=0.70
        )
        for cw in close_words:
            for full_name in _char_word_map.get(cw, []):
                matched_full_names.add(full_name)

    if not matched_full_names:
        return []

    # Fetch full documents for matched names
    results = []
    for full_name in list(matched_full_names)[:limit]:
        char = await db["characters"].find_one({"name": full_name})
        if char:
            results.append(char)
    return results