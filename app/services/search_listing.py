"""Bridges legacy list/search endpoints to the ranked SearchService.

Legacy endpoints return full MongoDB documents, so after ranking we load the
matched documents in ranked order. Their response shapes stay unchanged.
Delete once those modules are migrated to app/interfaces/http.
"""

from app.container import search_service
from app.db.mongo import get_db
from app.infrastructure.mongo.search_sources import SOURCES


async def ranked_documents(
    kind: str,
    query: str,
    limit: int,
    offset: int = 0,
    projection: dict | None = None,
) -> tuple[list[dict], int]:
    """(documents of `kind` best-matching `query`, total matches), best first."""
    ranked, total = await search_service().search_kind(query, kind, limit, offset)
    if not ranked:
        return [], total

    source = SOURCES[kind]
    ids = [d.id for d in ranked]
    cursor = get_db()[source.collection].find({"_id": {"$in": ids}}, projection)
    by_id = {str(doc["_id"]): doc async for doc in cursor}
    return [by_id[i] for i in ids if i in by_id], total
