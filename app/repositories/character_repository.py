from datetime import datetime, timedelta

from app.db.mongo import get_db

async def get_birthdays_by_date_range(start_date: str, end_date: str):
    db = get_db()
    
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return []
        
    if end_dt < start_dt:
        return []
        
    days = (end_dt - start_dt).days
    if days > 366:
        days = 366
        
    date_criteria = []
    for i in range(days + 1):
        dt = start_dt + timedelta(days=i)
        date_criteria.append({"birth_month": dt.month, "birth_day": dt.day})
        
    if not date_criteria:
        return []
        
    return await (
        db["characters"]
        .find(
            {
                "$or": date_criteria,
                "is_deleted": False
            },
            {
                "_id": 1,
                "name": 1,
                "images.profile": 1,
                "role": 1,
                "anime_ids": 1,
                "birth_month": 1,
                "birth_day": 1
            }
        )
        .to_list(None)
    )


async def get_all_characters():

    db = get_db()

    return await (
        db["characters"]
        .find({"is_deleted": False})
        .to_list(None)
    )


async def get_character_by_id(
    character_id: str
):

    db = get_db()

    return await (
        db["characters"]
        .find_one(
            {
                "_id": character_id,
                "is_deleted": False
            }
        )
    )


async def search_characters(
    query: str
):

    db = get_db()

    return await (
        db["characters"]
        .find(
            {
                "name": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": False
            }
        )
        .to_list(None)
    )

async def get_character_basic(
    character_id: str
):

    db = get_db()

    return await db["characters"].find_one(
        {
            "_id": character_id,
            "is_deleted": False
        },
        {
            "_id": 1,
            "name": 1,
            "images.profile": 1,
            "role": 1
        }
    )