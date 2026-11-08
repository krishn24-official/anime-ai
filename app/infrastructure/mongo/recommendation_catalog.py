"""RecommendationCatalog backed by MongoDB."""

from dataclasses import replace
from typing import Any, Callable

from app.domain.recommendations.entities import BaseTitle, Recommendation
from app.infrastructure.mongo.collections import CONTENT_COLLECTIONS
from app.infrastructure.mongo.content_catalog import summary_from_document

# Where each collection keeps the external id its recommendation source uses.
EXTERNAL_ID_FIELD = {
    "anime": "source_metadata.anilist_id",
    "manga": "source_metadata.anilist.id",
    "movie": "source_metadata.tmdb_id",
    "tv_series": "source_metadata.tmdb_id",
}


def _get(doc: dict, path: str):
    for part in path.split("."):
        doc = doc.get(part) if isinstance(doc, dict) else None
    return doc


class MongoRecommendationCatalog:
    def __init__(self, db_provider: Callable[[], Any]):
        self._db = db_provider

    async def base_title(self, content_type: str, content_id: str) -> BaseTitle | None:
        doc = await self._db()[CONTENT_COLLECTIONS[content_type]].find_one(
            {"_id": content_id, "is_deleted": {"$ne": True}},
            {"title": 1, "name": 1, "source_metadata": 1},
        )
        if not doc:
            return None
        external_id = _get(doc, EXTERNAL_ID_FIELD[content_type])
        return BaseTitle(
            content_type=content_type,
            content_id=content_id,
            title=summary_from_document(doc).title or content_id,
            external_id=external_id if isinstance(external_id, int) else None,
        )

    async def link(self, recs: list[Recommendation]) -> list[Recommendation]:
        """Attach our ids; drop titles we removed (e.g. as adult content)."""
        stored: dict[tuple[str, int], dict] = {}
        for content_type in {r.content_type for r in recs}:
            field = EXTERNAL_ID_FIELD[content_type]
            ids = [r.external_id for r in recs if r.content_type == content_type]
            async for doc in self._db()[CONTENT_COLLECTIONS[content_type]].find(
                {field: {"$in": ids}}, {"source_metadata": 1, "is_deleted": 1, "is_adult": 1}
            ):
                stored[(content_type, _get(doc, field))] = doc

        linked = []
        for rec in recs:
            doc = stored.get((rec.content_type, rec.external_id))
            if doc and (doc.get("is_deleted") or doc.get("is_adult")):
                continue
            linked.append(replace(rec, content_id=doc["_id"]) if doc else rec)
        return linked
