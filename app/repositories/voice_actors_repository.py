from app.db.mongo import get_db

async def get_voice_actor_by_id(voice_actor_id: str):
    db = get_db()
    return await db["voice_actors"].find_one(
        {"_id": voice_actor_id, "is_deleted": False}
    )

async def get_voice_actor_filmography(voice_actor_id: str):
    db = get_db()
    
    # Find all characters voiced by this voice actor
    characters = await db["characters"].find(
        {
            "voice_actor_ids": voice_actor_id,
            "is_deleted": False
        },
        {"_id": 1, "name": 1, "anime_ids": 1}
    ).to_list(None)
    
    # Collect unique anime_ids
    anime_to_character = {}
    for char in characters:
        for a_id in char.get("anime_ids", []):
            if a_id not in anime_to_character:
                anime_to_character[a_id] = char["name"]
                
    if not anime_to_character:
        return []
        
    anime_ids = list(anime_to_character.keys())
    
    # Fetch all corresponding anime
    animes = await db["anime"].find(
        {"_id": {"$in": anime_ids}, "is_deleted": False}
    ).to_list(None)
    
    result = []
    for anime in animes:
        result.append({
            "id": anime["_id"],
            "title": anime.get("title", {}).get("english") or anime.get("title", {}).get("romaji"),
            "year": anime.get("year", 0),
            "content_type": "anime",
            "poster": anime.get("images", {}).get("poster"),
            "role": f"as {anime_to_character[anime['_id']]}"
        })
        
    # Sort by year descending
    def safe_year(x):
        y = x.get("year")
        if not y:
            return 0
        try:
            return int(y)
        except (ValueError, TypeError):
            return 0
            
    result.sort(key=safe_year, reverse=True)
    return result
