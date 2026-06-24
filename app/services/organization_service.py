from app.repositories.organization_repository import (
    get_all_organizations,
    get_organization_by_id,
    search_organizations,
    get_organizations_by_anime,
)
from app.repositories.character_repository import get_character_basic
from app.db.mongo import get_db

def _serialize_basic_org(org: dict) -> dict:
    return {
        "id": str(org.get("_id")),
        "name": org.get("name"),
        "type": org.get("type"),
        "status": org.get("status"),
        "description": org.get("description"),
        "leader_id": org.get("leader_id"),
        "founded_by_id": org.get("founded_by_id"),
        "headquarters": org.get("headquarters"),
        "anime_ids": org.get("anime_ids", []),
        "manga_id": org.get("manga_id"),
        "images": org.get("images", {"logo": "", "banner": ""}),
        "tags": org.get("tags", []),
    }

async def fetch_all_organizations(type_filter: str | None = None, page: int = 1, limit: int = 20):
    items, total = await get_all_organizations(type_filter=type_filter, page=page, limit=limit)
    return {
        "items": [_serialize_basic_org(org) for org in items],
        "total": total,
        "page": page,
        "limit": limit,
    }

async def fetch_organization_details(org_id: str):
    org = await get_organization_by_id(org_id)
    if not org:
        return None

    # Resolve leader
    leader = None
    leader_id = org.get("leader_id")
    if leader_id:
        leader_char = await get_character_basic(leader_id)
        if leader_char:
            leader = {
                "id": leader_char["_id"],
                "name": leader_char["name"],
                "image": leader_char.get("images", {}).get("profile", "")
            }

    # Resolve founded_by
    founded_by = None
    founded_by_id = org.get("founded_by_id")
    if founded_by_id:
        founded_char = await get_character_basic(founded_by_id)
        if founded_char:
            founded_by = {
                "id": founded_char["_id"],
                "name": founded_char["name"],
                "image": founded_char.get("images", {}).get("profile", "")
            }

    # Resolve members
    members_list = []
    for member in org.get("members", []):
        char_id = member.get("char_id")
        char_basic = None
        if char_id:
            char_basic = await get_character_basic(char_id)
        
        character_details = None
        if char_basic:
            character_details = {
                "id": char_basic["_id"],
                "name": char_basic["name"],
                "image": char_basic.get("images", {}).get("profile", "")
            }
        
        members_list.append({
            "char_id": char_id,
            "title": member.get("title"),
            "order": member.get("order"),
            "character": character_details
        })

    # Resolve affiliated characters
    # 1. Start with explicitly specified affiliated characters in organization collection
    affiliated_chars_map = {}
    for aff in org.get("affiliated_characters", []):
        char_id = aff.get("char_id") or aff.get("id")
        if char_id:
            char_basic = await get_character_basic(char_id)
            if char_basic:
                affiliated_chars_map[char_id] = {
                    "id": char_basic["_id"],
                    "name": char_basic["name"],
                    "image": char_basic.get("images", {}).get("profile", ""),
                    "role": aff.get("role") or char_basic.get("role", "")
                }

    # 2. Add dynamic affiliations from characters who have this organization's name in their affiliations list
    org_name = org.get("name")
    if org_name:
        db = get_db()
        cursor = db["characters"].find({
            "affiliations": {"$regex": f"^{org_name}$", "$options": "i"},
            "is_deleted": False
        })
        async for char_doc in cursor:
            char_id = char_doc["_id"]
            if char_id not in affiliated_chars_map:
                affiliated_chars_map[char_id] = {
                    "id": char_id,
                    "name": char_doc["name"],
                    "image": char_doc.get("images", {}).get("profile", ""),
                    "role": char_doc.get("role", "")
                }

    return {
        "id": str(org["_id"]),
        "name": org.get("name"),
        "type": org.get("type"),
        "status": org.get("status"),
        "description": org.get("description"),
        "leader": leader,
        "founded_by": founded_by,
        "headquarters": org.get("headquarters"),
        "anime_ids": org.get("anime_ids", []),
        "manga_id": org.get("manga_id"),
        "images": org.get("images", {"logo": "", "banner": ""}),
        "tags": org.get("tags", []),
        "members": members_list,
        "affiliated_characters": list(affiliated_chars_map.values())
    }

async def fetch_organization_search(query: str):
    orgs = await search_organizations(query)
    # Search response shape: [{ id, name, type, images, anime_ids, manga_id }]
    return [
        {
            "id": str(org["_id"]),
            "name": org.get("name"),
            "type": org.get("type"),
            "images": org.get("images", {"logo": "", "banner": ""}),
            "anime_ids": org.get("anime_ids", []),
            "manga_id": org.get("manga_id"),
        }
        for org in orgs
    ]

async def fetch_organizations_by_anime(anime_id: str):
    orgs = await get_organizations_by_anime(anime_id)
    # Response: [{ id, name, type, images, status }]
    return [
        {
            "id": str(org["_id"]),
            "name": org.get("name"),
            "type": org.get("type"),
            "images": org.get("images", {"logo": "", "banner": ""}),
            "status": org.get("status"),
        }
        for org in orgs
    ]
