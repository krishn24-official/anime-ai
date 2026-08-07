from app.db.mongo import get_db
import re
from app.utils.search_utils import build_fuzzy_search_regex


async def get_all_manga(page: int = 1, limit: int = 50, search: str = None):

    db = get_db()
    skip = (page - 1) * limit
    
    query = {"is_deleted": False}
    if search:
        fuzzy_pattern = build_fuzzy_search_regex(search)
        search_regex = re.compile(fuzzy_pattern, re.IGNORECASE)
        query["$or"] = [
            {"name": search_regex},
            {"native_name": search_regex}
        ]

    items = await (
        db["manga"]
        .find(query)
        .sort([("name", 1)])
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["manga"].count_documents(query)

    return items, total


async def get_manga_by_id(
    manga_id: str
):

    db = get_db()

    return await (
        db["manga"]
        .find_one(
            {
                "_id": manga_id,
                "is_deleted": False
            }
        )
    )


async def search_manga(
    query: str
):

    db = get_db()

    fuzzy_pattern = build_fuzzy_search_regex(query)
    search_regex = re.compile(fuzzy_pattern, re.IGNORECASE)

    return await (
        db["manga"]
        .find(
            {
                "$or": [
                    {
                        "name": search_regex
                    },
                    {
                        "native_name": search_regex
                    }
                ]
            }
        )
        .to_list(None)
    )