from datetime import datetime, timezone

from app.db.mongo import get_db


VALID_CATEGORIES = ["Anime", "Games", "Movies", "TV Series"]


async def article_exists(url: str) -> bool:
    db = get_db()
    existing = await db["news"].find_one({"url": url}, {"_id": 1})
    return existing is not None


async def insert_article(article: dict):
    db = get_db()
    article["created_at"] = datetime.now(timezone.utc)
    await db["news"].insert_one(article)


async def get_latest_news(limit: int = 5):
    db = get_db()
    return await (
        db["news"]
        .find({"category": {"$in": VALID_CATEGORIES}})
        .sort("published_at", -1)
        .limit(limit)
        .to_list(None)
    )


async def get_news_by_category(
    category: str | None = None,
    page: int = 1,
    limit: int = 10,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    source: str | None = None,
):
    db = get_db()
    skip = (page - 1) * limit

    query = {}
    if category:
        query["category"] = category
    else:
        query["category"] = {"$in": VALID_CATEGORIES}

    if source:
        query["source"] = source

    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]

    if start_date or end_date:
        date_filter = {}
        if start_date:
            try:
                dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                date_filter["$gte"] = dt
            except ValueError:
                date_filter["$gte"] = start_date
        if end_date:
            try:
                end_str = f"{end_date}T23:59:59+00:00" if len(end_date) == 10 else end_date.replace("Z", "+00:00")
                dt = datetime.fromisoformat(end_str)
                date_filter["$lte"] = dt
            except ValueError:
                date_filter["$lte"] = end_date
        if date_filter:
            query["published_at"] = date_filter

    items = await (
        db["news"]
        .find(query)
        .sort("published_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["news"].count_documents(query)

    return items, total


async def get_news_by_id(news_id):
    db = get_db()
    return await db["news"].find_one({"_id": news_id})