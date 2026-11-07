import asyncio
from typing import Any, Callable

from app.domain.shared.content import ContentRef, ContentSummary
from app.infrastructure.mongo.collections import CONTENT_COLLECTIONS

# Fields needed to build a ContentSummary from any content collection.
SUMMARY_PROJECTION = {
    "title": 1,
    "name": 1,
    "images": 1,
    "poster": 1,
    "poster_image": 1,
    "cover_image": 1,
}


def summary_from_document(doc: dict) -> ContentSummary:
    """Collections store titles and posters in different shapes; normalise them."""
    title = None
    raw_title = doc.get("title")
    if raw_title:
        title = (
            raw_title
            if isinstance(raw_title, str)
            else raw_title.get("english") or raw_title.get("romaji")
        )
    if not title:
        title = doc.get("name")

    poster = doc.get("poster") or doc.get("poster_image") or doc.get("cover_image")
    if not poster and isinstance(doc.get("images"), dict):
        jpg = doc["images"].get("jpg", {})
        poster = (
            jpg.get("large_image_url")
            or jpg.get("image_url")
            or doc["images"].get("poster")
        )

    return ContentSummary(title=title, poster_image=poster)


class MongoContentCatalog:
    """ContentCatalog backed by the anime/manga/movies/tv_series collections."""

    def __init__(self, db_provider: Callable[[], Any]):
        self._db = db_provider

    async def get_summaries(
        self, refs: list[ContentRef]
    ) -> dict[ContentRef, ContentSummary]:
        ids_by_type: dict[str, set[str]] = {}
        for ref in refs:
            if ref.content_type in CONTENT_COLLECTIONS:
                ids_by_type.setdefault(ref.content_type, set()).add(ref.content_id)

        db = self._db()
        found: dict[ContentRef, ContentSummary] = {}

        async def fetch(content_type: str, ids: set[str]) -> None:
            cursor = db[CONTENT_COLLECTIONS[content_type]].find(
                {"_id": {"$in": list(ids)}}, SUMMARY_PROJECTION
            )
            async for doc in cursor:
                found[ContentRef(content_type, str(doc["_id"]))] = summary_from_document(doc)

        # One query per collection, run in parallel.
        await asyncio.gather(*(fetch(t, ids) for t, ids in ids_by_type.items()))
        return found
