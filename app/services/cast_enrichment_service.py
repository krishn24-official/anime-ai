import logging
from app.repositories import actors_repository

logger = logging.getLogger(__name__)

async def enrich_cast(cast: list[dict]) -> list[dict]:
    """
    Takes a raw cast list of {"actor_id": str, "character_name": str, "order": int}
    and enriches it with actual actor data.
    """
    if not cast:
        return []

    enriched = []
    
    for entry in cast:
        actor_id = entry.get("actor_id")
        character_name = entry.get("character_name", "Actor")
        order = entry.get("order", 0)
        
        if not actor_id:
            continue
            
        actor = await actors_repository.get_actor_by_id(actor_id)
        if not actor:
            logger.warning(f"Actor {actor_id} referenced in cast but not found (may be deleted).")
            continue
            
        profile_img = actor.get("images", {}).get("profile") if actor.get("images") else None
        
        enriched.append({
            "id": str(actor.get("_id")),
            "name": actor.get("name"),
            "image": profile_img,
            "role": character_name,
            "order": order
        })
        
    enriched.sort(key=lambda x: x.get("order", 0))
    
    # Remove the internal 'order' field before returning as it's not strictly needed for frontend layout once sorted,
    # but we can leave it just in case. Let's remove it to strictly match the expected shape if desired,
    # or leave it. Leaving it is harmless.
    for e in enriched:
        e.pop("order", None)
        
    return enriched
