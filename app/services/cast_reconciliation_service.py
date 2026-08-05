import asyncio
from datetime import datetime, timezone
import logging
from pymongo.errors import DuplicateKeyError

from app.db.mongo import get_db
from app.backend.utils.slug import create_slug
from app.repositories import actors_repository
from app.backend.ingestion.tmdb_client import get_person_details, image_url

logger = logging.getLogger(__name__)

async def resolve_or_create_actor(tmdb_person_id: int, name: str, profile_image: str | None) -> str | None:
    """
    Resolve an actor_id from a tmdb_person_id.
    If the actor doesn't exist, fetches TMDB to create a full record.
    Falls back to a minimal record if TMDB fetch fails.
    """
    if not tmdb_person_id:
        if not name:
            return None
        
        db = get_db()
        name = name.strip()
        # Explicit path for when tmdb_person_id is None (legacy-backfill)
        # Attempt an exact name match against existing actors (case-insensitive and ignore trailing spaces)
        import re
        existing = await db["actors"].find_one({"name": re.compile(f"^{re.escape(name)}\\s*$", re.IGNORECASE), "is_deleted": False})
        if existing:
            return str(existing["_id"])
            
        # Create minimal actor record with just name
        slug = create_slug(name)
        if not slug:
            import uuid
            slug = str(uuid.uuid4())[:8]
            
        base_actor_id = f"actor_{slug}"
        actor_id = base_actor_id
        counter = 1
        
        while True:
            while await db["actors"].find_one({"_id": actor_id}):
                actor_id = f"{base_actor_id}_{counter}"
                counter += 1
                
            doc = {
                "_id": actor_id,
                "tmdb_id": None,
                "name": name,
                "birthdate": None,
                "biography": None,
                "images": {
                    "profile": None
                },
                "is_deleted": False,
                "deleted_at": None,
                "source_metadata": {
                    "source": "legacy_backfill",
                    "created_by": "reconciliation_script",
                    "created_at": datetime.now(timezone.utc)
                }
            }
            
            try:
                await actors_repository.create_actor(doc)
                break
            except DuplicateKeyError:
                counter += 1
                actor_id = f"{base_actor_id}_{counter}"
                
        return actor_id

    db = get_db()
    
    # 1. Lookup existing by tmdb_id
    existing = await db["actors"].find_one({"tmdb_id": tmdb_person_id, "is_deleted": False})
    if existing:
        return str(existing["_id"])

    # 2. Try fetching full details from TMDB
    person_data = await get_person_details(tmdb_person_id)
    
    birthdate = None
    biography = None
    # Use higher-res profile if available from TMDB person fetch
    image = profile_image
    
    if person_data:
        birthdate = person_data.get("birthday")
        biography = person_data.get("biography")
        tmdb_profile = person_data.get("profile_path")
        if tmdb_profile:
            image = image_url(tmdb_profile, "original")
            
    if not name and person_data:
        name = person_data.get("name")
        
    if not name:
        return None # Can't create without a name
        
    name = name.strip()

    # Check if an actor with this name already exists (e.g. legacy backfill without tmdb_id)
    # We use regex to match case-insensitively and ignore trailing spaces just in case
    import re
    existing_by_name = await db["actors"].find_one({"name": re.compile(f"^{re.escape(name)}\\s*$", re.IGNORECASE), "is_deleted": False})
    if existing_by_name:
        update_data = {}
        if not existing_by_name.get("tmdb_id"):
            update_data["tmdb_id"] = tmdb_person_id
        if not existing_by_name.get("birthdate") and birthdate:
            update_data["birthdate"] = birthdate
        if not existing_by_name.get("biography") and biography:
            update_data["biography"] = biography
        
        # Check if profile image is missing
        current_image = existing_by_name.get("images", {}).get("profile")
        if not current_image and image:
            update_data["images.profile"] = image
            
        if update_data:
            await db["actors"].update_one(
                {"_id": existing_by_name["_id"]},
                {"$set": update_data}
            )
        return str(existing_by_name["_id"])

    # Generate slug & unique ID
    slug = create_slug(name)
    if not slug:
        import uuid
        slug = f"tmdb-{tmdb_person_id}" if tmdb_person_id else str(uuid.uuid4())[:8]
        
    base_actor_id = f"actor_{slug}"
    actor_id = base_actor_id
    counter = 1

    # Retry loop for DuplicateKeyError in concurrent executions
    while True:
        while await db["actors"].find_one({"_id": actor_id}):
            actor_id = f"{base_actor_id}_{counter}"
            counter += 1

        # Create actor
        doc = {
            "_id": actor_id,
            "tmdb_id": tmdb_person_id,
            "name": name,
            "birthdate": birthdate,
            "biography": biography,
            "images": {
                "profile": image
            },
            "is_deleted": False,
            "deleted_at": None,
            "source_metadata": {
                "source": "tmdb",
                "created_by": "ingestion_script",
                "created_at": datetime.now(timezone.utc)
            }
        }
        
        try:
            await actors_repository.create_actor(doc)
            break
        except DuplicateKeyError:
            # Another concurrent request grabbed this ID, try again with next counter
            counter += 1
            actor_id = f"{base_actor_id}_{counter}"

    return actor_id


async def reconcile_cast(raw_cast: list[dict]) -> list[dict]:
    """
    Converts raw cast shape into the unified shape matching manual edits:
    Input: {tmdb_person_id, name, character, profile_image}
    Output: {actor_id, character_name, order}
    """
    if not raw_cast:
        return []

    # Run resolution concurrently
    tasks = []
    for entry in raw_cast:
        tmdb_person_id = entry.get("tmdb_person_id")
        name = entry.get("name")
        profile_image = entry.get("profile_image")
        tasks.append(resolve_or_create_actor(tmdb_person_id, name, profile_image))

    actor_ids = await asyncio.gather(*tasks)

    reconciled = []
    for i, (entry, actor_id) in enumerate(zip(raw_cast, actor_ids)):
        if actor_id:
            reconciled.append({
                "actor_id": actor_id,
                "character_name": entry.get("character") or "Actor",
                "order": i
            })

    return reconciled


async def reconcile_directors(raw_directors: list[dict]) -> list[dict]:
    """
    Converts raw directors shape into the unified shape matching manual edits:
    Input: {tmdb_person_id, name, profile_image}
    Output: {actor_id, order}
    """
    if not raw_directors:
        return []

    # Run resolution concurrently
    tasks = []
    for entry in raw_directors:
        tmdb_person_id = entry.get("tmdb_person_id")
        name = entry.get("name")
        profile_image = entry.get("profile_image")
        tasks.append(resolve_or_create_actor(tmdb_person_id, name, profile_image))

    actor_ids = await asyncio.gather(*tasks)

    reconciled = []
    for i, actor_id in enumerate(actor_ids):
        if actor_id:
            reconciled.append({
                "actor_id": actor_id,
                "order": i
            })

    return reconciled


async def reconcile_creators(raw_creators: list[dict]) -> list[dict]:
    """
    Converts raw creators shape into the unified shape matching manual edits:
    Input: {tmdb_person_id, name, profile_image}
    Output: {actor_id, order}
    """
    if not raw_creators:
        return []

    # Run resolution concurrently
    tasks = []
    for entry in raw_creators:
        tmdb_person_id = entry.get("tmdb_person_id")
        name = entry.get("name")
        profile_image = entry.get("profile_image")
        tasks.append(resolve_or_create_actor(tmdb_person_id, name, profile_image))

    actor_ids = await asyncio.gather(*tasks)

    reconciled = []
    for i, actor_id in enumerate(actor_ids):
        if actor_id:
            reconciled.append({
                "actor_id": actor_id,
                "order": i
            })

    return reconciled


async def reconcile_writers(raw_writers: list[dict]) -> list[dict]:
    """
    Converts raw writers shape into the unified shape matching manual edits:
    Input: {tmdb_person_id, name, profile_image}
    Output: {actor_id, order}
    """
    if not raw_writers:
        return []

    # Run resolution concurrently
    tasks = []
    for entry in raw_writers:
        tmdb_person_id = entry.get("tmdb_person_id")
        name = entry.get("name")
        profile_image = entry.get("profile_image")
        tasks.append(resolve_or_create_actor(tmdb_person_id, name, profile_image))

    actor_ids = await asyncio.gather(*tasks)

    reconciled = []
    for i, actor_id in enumerate(actor_ids):
        if actor_id:
            reconciled.append({
                "actor_id": actor_id,
                "order": i
            })

    return reconciled
