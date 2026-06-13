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


async def get_news_by_category(category: str, page: int = 1, limit: int = 10):
    db = get_db()
    skip = (page - 1) * limit

    query = {}
    if category:
        query["category"] = category
    else:
        query["category"] = {"$in": VALID_CATEGORIES}

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