import re
from app.services.relationship_inverse_map import get_inverse_relationship
from app.db.mongo import get_db

def _slug(text: str) -> str:
    """Simplify a character _id into a short slug for building relationship _ids."""
    text = text.replace("char_", "")
    text = re.sub(r"[^a-z0-9_]", "", text.lower())
    return text


def _make_rel_id(source_id: str, target_id: str, relationship: str) -> str:
    rel_word = re.sub(r"[^a-z0-9_]", "_", relationship.strip().lower())
    return f"rel_{_slug(source_id)}_{_slug(target_id)}_{rel_word}"


def build_relationship_pair(
    source_id: str, 
    target_id: str, 
    relationship: str, 
    rel_type: str | None, 
    context: str | None, 
    explicit_inverse: str | None
) -> tuple[dict, dict | None]:
    """Returns (forward_doc, inverse_doc). Inverse is None if either entity is not a character."""
    source_id = source_id.strip()
    target_id = target_id.strip()
    relationship = relationship.strip().lower()
    rel_type = rel_type.strip() if rel_type else None
    context = context.strip() if context else None
    explicit_inverse = explicit_inverse.strip() if explicit_inverse else None

    forward_id = _make_rel_id(source_id, target_id, relationship)
    
    is_char_to_char = source_id.startswith("char_") and target_id.startswith("char_")
    
    if is_char_to_char:
        inverse_relationship = get_inverse_relationship(relationship, explicit_inverse)
        inverse_id = _make_rel_id(target_id, source_id, inverse_relationship)
    else:
        inverse_relationship = None
        inverse_id = None

    forward_doc = {
        "_id": forward_id,
        "source_id": source_id,
        "target_id": target_id,
        "relationship": relationship,
        "type": rel_type,
        "context": context,
        "is_deleted": False,
        "deleted_at": None,
        "inverse_of": inverse_id,
    }

    if not is_char_to_char:
        return forward_doc, None

    inverse_doc = {
        "_id": inverse_id,
        "source_id": target_id,
        "target_id": source_id,
        "relationship": inverse_relationship,
        "type": rel_type,
        "context": context,
        "is_deleted": False,
        "deleted_at": None,
        "inverse_of": forward_id,
    }

    return forward_doc, inverse_doc


async def resolve_entity_type(entity_id: str) -> str | None:
    db = get_db()
    
    if entity_id.startswith("char_"):
        col = "characters"
        ent_type = "character"
    elif entity_id.startswith("org_"):
        col = "organizations"
        ent_type = "organization"
    elif entity_id.startswith("anime_"):
        col = "anime"
        ent_type = "anime"
    elif entity_id.startswith("manga_"):
        col = "manga"
        ent_type = "manga"
    elif entity_id.startswith("movie_"):
        col = "movies"
        ent_type = "movie"
    elif entity_id.startswith("tv_"):
        col = "tv_series"
        ent_type = "tv_series"
    else:
        return None
        
    doc = await db[col].find_one({"_id": entity_id, "is_deleted": {"$ne": True}})
    if doc:
        return ent_type
    return None


async def check_relationship_exists(source_id: str, target_id: str, relationship: str):
    from app.repositories.relationship_repository import find_exact_relationship
    return await find_exact_relationship(source_id, target_id, relationship)


async def create_relationship(
    admin_id: str,
    source_id: str,
    target_id: str,
    relationship: str,
    rel_type: str | None,
    context: str | None,
    explicit_inverse: str | None,
    overwrite: bool = False
):
    from app.backend.constants.anime_enums import RELATIONSHIP_TYPES
    
    if rel_type and rel_type not in RELATIONSHIP_TYPES:
        raise ValueError(f"Invalid relationship type. Must be one of {RELATIONSHIP_TYPES}")
        
    if source_id == target_id:
        raise ValueError("source_id and target_id cannot be the same")
        
    source_type = await resolve_entity_type(source_id)
    if not source_type:
        raise ValueError(f"Source entity {source_id} not found or unrecognized")
        
    target_type = await resolve_entity_type(target_id)
    if not target_type:
        raise ValueError(f"Target entity {target_id} not found or unrecognized")
            
    existing = await check_relationship_exists(source_id, target_id, relationship)
    
    if existing and not overwrite:
        return {
            "status": "duplicate",
            "existing": existing
        }
        
    docs = [d for d in build_relationship_pair(source_id, target_id, relationship, rel_type, context, explicit_inverse) if d is not None]
    
    db = get_db()
    col = db["relationships"]
    for doc in docs:
        await col.replace_one(
            {"_id": doc["_id"]},
            doc,
            upsert=True
        )
        
    return {
        "status": "overwritten" if existing else "created",
        "docs": docs
    }
