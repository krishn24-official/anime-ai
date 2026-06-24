from app.db.mongo import get_db

async def get_all_organizations(type_filter: str | None = None, page: int = 1, limit: int = 20):
    db = get_db()
    query = {"is_deleted": {"$ne": True}}
    if type_filter:
        query["type"] = type_filter

    total = await db["organizations"].count_documents(query)
    skip = (page - 1) * limit
    items = await db["organizations"].find(query).skip(skip).limit(limit).to_list(None)
    return items, total

async def get_organization_by_id(org_id: str):
    db = get_db()
    return await db["organizations"].find_one({"_id": org_id, "is_deleted": {"$ne": True}})

async def search_organizations(query_str: str):
    db = get_db()
    cursor = db["organizations"].find({
        "$or": [
            {"name": {"$regex": query_str, "$options": "i"}},
            {"description": {"$regex": query_str, "$options": "i"}},
        ],
        "is_deleted": {"$ne": True}
    })
    return await cursor.to_list(None)

async def get_organizations_by_anime(anime_id: str):
    db = get_db()
    cursor = db["organizations"].find({
        "anime_ids": anime_id,
        "is_deleted": {"$ne": True}
    })
    return await cursor.to_list(None)

async def find_organizations_by_names(names: list[str]):
    db = get_db()
    if not names:
        return []
    
    # We want a case-insensitive match for affiliations
    # We can construct regexes or matching conditions. Since name list is usually small,
    # let's construct case-insensitive regexes for each name, or simply query all and filter in python.
    # Actually, using a regex $in list is easiest:
    regex_list = [{"name": {"$regex": f"^{names_item}$", "$options": "i"}} for names_item in names]
    if not regex_list:
        return []
    cursor = db["organizations"].find({
        "$or": regex_list,
        "is_deleted": {"$ne": True}
    })
    return await cursor.to_list(None)
