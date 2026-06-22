from app.repositories.manual_news_repository import (
    create_manual_news,
    get_manual_news_by_id,
    update_manual_news,
    delete_manual_news,
)
from app.services.cloudinary_service import upload_image_from_bytes

VALID_CATEGORIES = {"Anime", "Games", "Movies", "TV Series"}


def _serialize(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title"),
        "description": doc.get("description"),
        "category": doc.get("category"),
        "images": doc.get("images", []),
        "author_id": str(doc.get("author_id")) if doc.get("author_id") else None,
        "author_name": doc.get("author_name"),
        "source": doc.get("source"),
        "published_at": doc.get("published_at") or doc.get("created_at"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def create_news_post(
    title: str,
    description: str,
    category: str,
    author_id,
    author_name: str,
    image_files: list[tuple[bytes, str]],   # list of (file_bytes, filename)
):
    if not title or not title.strip():
        return None, "Title is required"

    if not description or not description.strip():
        return None, "Description is required"

    if category not in VALID_CATEGORIES:
        return None, f"Category must be one of: {', '.join(VALID_CATEGORIES)}"

    # Upload images to Cloudinary
    image_urls = []
    for file_bytes, filename in image_files:
        url = await upload_image_from_bytes(
            file_bytes,
            folder="entertainment_hub/manual_news",
        )
        if url:
            image_urls.append(url)

    doc = {
        "title": title.strip(),
        "description": description.strip(),
        "summary": description.strip()[:240],
        "category": category,
        "images": image_urls,
        "image_url": image_urls[0] if image_urls else None,  # first image for card display
        "author_id": author_id,
        "author_name": author_name,
    }

    result = await create_manual_news(doc)

    # published_at defaults to created_at for manual posts
    if not result.get("published_at"):
        result["published_at"] = result["created_at"]

    try:
        from app.services.websocket_manager import manager
        from app.services.news_service import _serialize as serialize_news
        await manager.broadcast({
            "type": "NEW_ARTICLE",
            "data": serialize_news(result)
        })
    except Exception as ws_err:
        print("[manual_news_service] websocket broadcast error:", ws_err)

    return _serialize(result), None


async def fetch_manual_news(news_id: str):
    doc = await get_manual_news_by_id(news_id)
    if not doc:
        return None
    return _serialize(doc)


async def update_news_post(
    news_id: str,
    title: str | None,
    description: str | None,
    category: str | None,
):
    updates = {}

    if title is not None:
        if not title.strip():
            return None, "Title cannot be empty"
        updates["title"] = title.strip()

    if description is not None:
        if not description.strip():
            return None, "Description cannot be empty"
        updates["description"] = description.strip()
        updates["summary"] = description.strip()[:240]

    if category is not None:
        if category not in VALID_CATEGORIES:
            return None, f"Category must be one of: {', '.join(VALID_CATEGORIES)}"
        updates["category"] = category

    if not updates:
        return None, "No fields to update"

    result = await update_manual_news(news_id, updates)

    if not result:
        return None, "News post not found"

    return _serialize(result), None


async def remove_news_post(news_id: str):
    deleted = await delete_manual_news(news_id)
    if not deleted:
        return False, "News post not found"
    return True, None