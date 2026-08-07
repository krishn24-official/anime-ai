import re
from app.db.mongo import get_db

def normalize_title(s: str) -> str:
    """Lowercase and remove non-alphanumeric characters."""
    if not s:
        return ""
    return re.sub(r'[^a-z0-9]', '', s.lower())

def build_loose_regex(s: str) -> str:
    """Split by non-alphanumeric and join with .* for loose regex matching."""
    if not s:
        return ""
    parts = re.split(r'[^a-zA-Z0-9]+', s)
    parts = [re.escape(p) for p in parts if p]
    if not parts:
        return ""
    return ".*".join(parts)

def get_possible_titles(doc: dict, content_type: str) -> list[str]:
    titles = []
    if content_type == "anime":
        title_obj = doc.get("title", {})
        if title_obj.get("english"):
            titles.append(title_obj["english"])
        if title_obj.get("romaji"):
            titles.append(title_obj["romaji"])
    else:
        # movie or tv_series
        if doc.get("title"):
            titles.append(doc["title"])
        if doc.get("original_title"):
            titles.append(doc["original_title"])
    return titles

async def find_cross_collection_duplicate(title: str, year: int, source_type: str) -> dict | None:
    """
    Search other collections for a matching normalized title within ±1 year.
    Returns {"content_type": ..., "content_id": ...} if a match is found, else None.
    """
    if not title:
        return None
        
    db = get_db()
    norm_title = normalize_title(title)
    if not norm_title:
        return None
        
    loose_regex = build_loose_regex(title)
    if not loose_regex:
        return None
        
    year = year or 0
    # Create year range ±1 (both int and string)
    year_range = []
    if year > 0:
        year_range = [
            int(year) - 1, int(year), int(year) + 1,
            str(int(year) - 1), str(int(year)), str(int(year) + 1)
        ]
    
    # Define targets to check based on source_type
    targets = []
    if source_type == "anime":
        targets = ["movies", "tv_series"]
    elif source_type == "movie":
        targets = ["anime", "tv_series"]
    elif source_type == "tv_series":
        targets = ["anime", "movies"]
        
    for target in targets:
        query = {
            "is_deleted": {"$ne": True}
        }
        
        # Build title query
        if target == "anime":
            query["$or"] = [
                {"title.english": {"$regex": loose_regex, "$options": "i"}},
                {"title.romaji": {"$regex": loose_regex, "$options": "i"}}
            ]
        else:
            query["$or"] = [
                {"title": {"$regex": loose_regex, "$options": "i"}},
                {"original_title": {"$regex": loose_regex, "$options": "i"}}
            ]
            
        if year_range:
            query["year"] = {"$in": year_range}
            
        candidates = await db[target].find(query).to_list(None)
        
        target_content_type = target
        if target == "movies":
            target_content_type = "movie"
            
        for cand in candidates:
            cand_titles = get_possible_titles(cand, target_content_type)
            for ct in cand_titles:
                if normalize_title(ct) == norm_title:
                    return {
                        "content_type": target_content_type,
                        "content_id": cand["_id"]
                    }
                    
    return None

async def check_for_duplicate(doc: dict, content_type: str) -> dict | None:
    """
    Checks if a document is a duplicate of something in another collection.
    Returns the duplicate metadata or None.
    """
    titles = get_possible_titles(doc, content_type)
    year = doc.get("year", 0)
    try:
        year = int(year) if year else 0
    except (ValueError, TypeError):
        year = 0
    
    for title in titles:
        dup = await find_cross_collection_duplicate(title, year, content_type)
        if dup:
            return dup
            
    return None

async def apply_reciprocal_duplicate_flag(source_id: str, source_type: str, dup: dict):
    """
    Applies a reciprocal 'possible_duplicate_of' flag to the target document.
    So if source_id is a duplicate of target, the target is marked as a duplicate of source_id.
    """
    from app.db.mongo import get_db
    db = get_db()
    
    target_coll = dup["content_type"]
    target_id = dup["content_id"]
    
    if target_coll == "tv_series":
        target_coll_name = "tv_series"
    elif target_coll == "movie":
        target_coll_name = "movies"
    elif target_coll == "anime":
        target_coll_name = "anime"
    else:
        return
        
    reciprocal_dup = {
        "content_type": source_type,
        "content_id": source_id
    }
    
    await db[target_coll_name].update_one(
        {"_id": target_id},
        {"$set": {"possible_duplicate_of": reciprocal_dup}}
    )
