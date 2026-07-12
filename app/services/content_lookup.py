from app.db.mongo import get_db

CONTENT_COLLECTION_MAP = {
    "anime": "anime",
    "manga": "manga",
    "movie": "movies",
    "tv_series": "tv_series",
}

async def resolve_content_title(content_type: str, content_id: str) -> dict | None:
    """
    Returns a dict with 'title' and 'poster_image' if found, else None.
    """
    db = get_db()
    col = CONTENT_COLLECTION_MAP.get(content_type)
    if not col:
        return None

    doc = await db[col].find_one(
        {"_id": content_id}, 
        {"title": 1, "name": 1, "images": 1, "poster": 1, "poster_image": 1, "cover_image": 1}
    )
    
    if not doc:
        return None

    title = None
    if doc.get("title"):
        if isinstance(doc["title"], str):
            title = doc["title"]
        else:
            title = doc["title"].get("english") or doc["title"].get("romaji")
            
    if not title:
        title = doc.get("name")
    
    poster_image = None
    if doc.get("poster"):
        poster_image = doc["poster"]
    elif doc.get("poster_image"):
        poster_image = doc["poster_image"]
    elif doc.get("cover_image"):
        poster_image = doc["cover_image"]
    elif doc.get("images") and isinstance(doc["images"], dict):
        jpg = doc["images"].get("jpg", {})
        poster_image = jpg.get("large_image_url") or jpg.get("image_url")
        if not poster_image:
            poster_image = doc["images"].get("poster")
    
    return {
        "title": title or content_id,
        "poster_image": poster_image
    }
