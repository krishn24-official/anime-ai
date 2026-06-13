from bson import ObjectId
from bson.errors import InvalidId

from app.repositories.news_repository import (
    get_latest_news,
    get_news_by_category,
    get_news_by_id,
)


def _serialize(article: dict) -> dict:
    return {
        "id": str(article.get("_id")),
        "title": article.get("title"),
        "url": article.get("url"),
        "source": article.get("source"),
        "category": article.get("category"),
        "summary": article.get("summary"),
        "description": article.get("description"),
        "image_url": article.get("image_url"),
        "published_at": article.get("published_at"),
    }


async def fetch_latest_news(limit: int = 5):
    articles = await get_latest_news(limit=limit)
    return [_serialize(a) for a in articles]


async def fetch_news_by_category(category: str = None, page: int = 1, limit: int = 10):
    items, total = await get_news_by_category(category=category, page=page, limit=limit)

    return {
        "items": [_serialize(a) for a in items],
        "total": total,
        "page": page,
        "limit": limit,
    }


async def fetch_news_detail(news_id: str):
    try:
        oid = ObjectId(news_id)
    except InvalidId:
        return None

    article = await get_news_by_id(oid)
    if not article:
        return None

    return _serialize(article)