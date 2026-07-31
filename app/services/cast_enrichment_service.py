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


async def enrich_crew(crew_list: list[dict | str], default_role: str = "Crew") -> list[dict]:
    """
    Takes a raw crew list (directors/creators) which might be mixed legacy strings or 
    new {"actor_id": str, "order": int} dicts, and enriches it.
    """
    if not crew_list:
        return []

    enriched = []
    
    for i, entry in enumerate(crew_list):
        # Handle legacy string format
        if isinstance(entry, str):
            enriched.append({
                "id": entry,
                "name": entry,
                "image": None,
                "role": default_role,
                "order": i
            })
            continue

        # Handle new dict format
        actor_id = entry.get("actor_id")
        order = entry.get("order", i)
        
        if not actor_id:
            continue
            
        actor = await actors_repository.get_actor_by_id(actor_id)
        if not actor:
            logger.warning(f"Actor {actor_id} referenced in crew but not found (may be deleted).")
            continue
            
        profile_img = actor.get("images", {}).get("profile") if actor.get("images") else None
        
        enriched.append({
            "id": str(actor.get("_id")),
            "name": actor.get("name"),
            "image": profile_img,
            "role": default_role,
            "order": order
        })
        
    enriched.sort(key=lambda x: x.get("order", 0))
    
    for e in enriched:
        e.pop("order", None)
        
    return enriched
