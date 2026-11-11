import re
from datetime import datetime, timezone

from app.db.mongo import get_db

VALID_CATEGORIES = ["Anime", "Games", "Movies", "TV Series"]

# Articles that are another source's copy of a stored story are kept (so their URL
# is never fetched again) but linked to the original and hidden from listings.
ORIGINALS = {"duplicate_of": {"$exists": False}}


def normalize_category(cat: str | None) -> str | None:
    if not cat:
        return None
    cat_clean = cat.strip()
    if cat_clean.lower() in ["all", ""]:
        return None
    if cat_clean.lower() in ["tv-series", "tv series", "tv_series", "tvseries"]:
        return "TV Series"
    for valid in VALID_CATEGORIES:
        if valid.lower() == cat_clean.lower():
            return valid
    return cat_clean


async def article_exists(url: str) -> bool:
    db = get_db()
    existing = await db["news"].find_one({"url": url}, {"_id": 1})
    return existing is not None


async def insert_article(article: dict):
    db = get_db()
    article["created_at"] = datetime.now(timezone.utc)
    await db["news"].insert_one(article)


async def recent_originals(since: datetime) -> list[dict]:
    """Listed articles published since `since` (id, source, title, published_at), oldest first."""
    return await get_db()["news"].find(
        {**ORIGINALS, "published_at": {"$gte": since}}, {"title": 1, "source": 1, "published_at": 1}
    ).sort("published_at", 1).to_list(None)


async def insert_duplicate(article: dict, original_id) -> None:
    """Store a lightweight record of another source's copy and credit that source."""
    db = get_db()
    await db["news"].insert_one({
        "url": article.get("url"),
        "title": article.get("title"),
        "source": article.get("source"),
        "published_at": article.get("published_at"),
        "duplicate_of": original_id,
        "created_at": datetime.now(timezone.utc),
    })
    await db["news"].update_one(
        {"_id": original_id},
        {"$addToSet": {"also_reported_by": {"source": article.get("source"), "url": article.get("url")}}},
    )


async def get_latest_news(limit: int = 5):
    db = get_db()
    return await (
        db["news"]
        .find({**ORIGINALS, "category": {"$in": VALID_CATEGORIES}})
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

    category = normalize_category(category)

    query = dict(ORIGINALS)
    if category:
        query["category"] = category
    else:
        query["category"] = {"$in": VALID_CATEGORIES}

    if source:
        query["source"] = source

    if search and search.strip():
        # Free-text "contains" match over articles; escaped so input like "(" is literal.
        pattern = re.escape(search.strip())
        query["$or"] = [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"summary": {"$regex": pattern, "$options": "i"}},
            {"description": {"$regex": pattern, "$options": "i"}},
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
                end_str = (
                    f"{end_date}T23:59:59+00:00"
                    if len(end_date) == 10
                    else end_date.replace("Z", "+00:00")
                )
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
