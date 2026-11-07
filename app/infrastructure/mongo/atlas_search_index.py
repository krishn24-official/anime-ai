"""SearchIndex backed by MongoDB Atlas Search on the `search_catalog` collection.

Index-backed and fast, with autocomplete and typo tolerance. Requires the index
from search_catalog.INDEX_DEFINITION and a populated catalog
(python -m app.scripts.build_search_catalog). Kinds that are not in the catalog,
or any failure, raise SearchIndexUnavailable so FallbackSearchIndex uses regex.
"""

import time
from typing import Any, Callable

from app.domain.search import rules
from app.domain.search.entities import SearchDocument
from app.domain.search.ports import SearchIndexUnavailable
from app.infrastructure.mongo.search_catalog import COLLECTION, INDEX_NAME
from app.infrastructure.mongo.search_sources import SOURCES

READINESS_TTL_SECONDS = 60


class AtlasSearchIndex:
    def __init__(self, db_provider: Callable[[], Any], kinds: tuple[str, ...]):
        self._db = db_provider
        self._kinds = set(kinds)
        self._ready: bool | None = None
        self._checked_at = 0.0

    async def _ensure_ready(self, kind: str) -> None:
        if kind not in self._kinds:
            raise SearchIndexUnavailable(f"'{kind}' is not in the search catalog")
        # $search on a missing or building index silently returns nothing, so
        # check readiness explicitly (cached) and let the caller fall back.
        if self._ready is None or time.monotonic() - self._checked_at > READINESS_TTL_SECONDS:
            self._ready = await self._check_ready()
            self._checked_at = time.monotonic()
        if not self._ready:
            raise SearchIndexUnavailable(f"Atlas Search index '{INDEX_NAME}' is not ready")

    async def _check_ready(self) -> bool:
        try:
            col = self._db()[COLLECTION]
            indexes = await (await col.list_search_indexes(INDEX_NAME)).to_list(None)
            if not indexes or not indexes[0].get("queryable"):
                return False
            return await col.estimated_document_count() > 0
        except Exception:
            return False  # not on Atlas, no permissions, network error, ...

    async def candidates(
        self, query: str, kind: str, limit: int, fuzzy: bool
    ) -> list[SearchDocument]:
        await self._ensure_ready(kind)

        q, qc = rules.normalize(query), rules.compact(query)
        should = [
            {"text": {"query": q, "path": ["title", "aliases"], "score": {"boost": {"value": 5}}}},
            {"autocomplete": {"query": q, "path": "title", "score": {"boost": {"value": 3}}}},
            {"autocomplete": {"query": q, "path": "aliases"}},
            {"autocomplete": {"query": qc, "path": "names_compact"}},
        ]
        if fuzzy:
            typo = {"maxEdits": 1 if len(qc) < 7 else 2, "prefixLength": 1}
            should += [
                {"text": {"query": q, "path": ["title", "aliases"], "fuzzy": typo}},
                {"autocomplete": {"query": q, "path": "title", "fuzzy": typo}},
            ]

        pipeline = [
            {
                "$search": {
                    "index": INDEX_NAME,
                    "compound": {
                        "filter": [{"equals": {"path": "kind", "value": kind}}],
                        "should": should,
                        "minimumShouldMatch": 1,
                    },
                }
            },
            {"$limit": limit},
            {"$project": {"ref_id": 1}},
        ]
        cursor = await self._db()[COLLECTION].aggregate(pipeline)
        ids = [row["ref_id"] for row in await cursor.to_list(None)]
        return await self._load(kind, ids)

    async def _load(self, kind: str, ids: list[str]) -> list[SearchDocument]:
        """Load the matched items from their source collection (keeps Atlas order)."""
        if not ids:
            return []
        source = SOURCES[kind]
        cursor = self._db()[source.collection].find(
            {"_id": {"$in": ids}, **source.not_deleted}, source.projection
        )
        by_id = {}
        async for raw in cursor:
            doc = source.to_document(raw)
            if doc:
                by_id[doc.id] = doc
        return [by_id[i] for i in ids if i in by_id]
