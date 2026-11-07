"""The `search_catalog` collection: one small document per searchable item, backed
by a single Atlas Search index.

One collection + one index (instead of one per source collection) keeps queries
simple and stays within the search-index limits of small Atlas tiers. Rows hold
only what matching and ranking need (no display fields), to keep storage small;
AtlasSearchIndex loads display fields from the source collections for results.

Kept in sync by:
  - rebuild(): full rebuild (scheduler + app/scripts/build_search_catalog.py)
  - refresh(kind, id): after admin create/update/delete
"""

import logging
import uuid
from typing import Any, Callable

import bson
from pymongo import ReplaceOne
from pymongo.operations import SearchIndexModel

from app.domain.search import rules
from app.domain.search.entities import SearchDocument
from app.infrastructure.mongo.search_sources import SOURCES

logger = logging.getLogger(__name__)

COLLECTION = "search_catalog"
INDEX_NAME = "catalog_search"
BATCH_SIZE = 1000
_ID_INDEX_BYTES_PER_DOC = 60  # rough size of a row in the default _id index

_AUTOCOMPLETE = {
    "type": "autocomplete",
    "tokenization": "edgeGram",
    "minGrams": 2,
    "maxGrams": 15,
    "foldDiacritics": True,
}

INDEX_DEFINITION = {
    "mappings": {
        "dynamic": False,
        "fields": {
            "kind": {"type": "token"},
            "title": [{"type": "string", "analyzer": "lucene.standard"}, _AUTOCOMPLETE],
            "aliases": [{"type": "string", "analyzer": "lucene.standard"}, _AUTOCOMPLETE],
            # Names without spaces/punctuation, so "spiderman" finds "Spider-Man".
            "names_compact": {**_AUTOCOMPLETE, "maxGrams": 20},
        },
    }
}


def catalog_id(kind: str, ref_id: str) -> str:
    return f"{kind}:{ref_id}"


def to_catalog_document(doc: SearchDocument, build_id: str | None = None) -> dict:
    names = [doc.title, *doc.aliases]
    return {
        "_id": catalog_id(doc.kind, doc.id),
        "kind": doc.kind,
        "ref_id": doc.id,
        "title": doc.title,
        "aliases": list(doc.aliases),
        "names_compact": list(dict.fromkeys(c for c in map(rules.compact, names) if c)),
        "rating": doc.rating,
        "popularity": doc.popularity,
        "build_id": build_id,
    }


class StorageQuotaError(RuntimeError):
    """Building the catalog would exceed the cluster's storage quota."""


class MongoSearchCatalog:
    def __init__(self, db_provider: Callable[[], Any], kinds: tuple[str, ...]):
        self._db = db_provider
        self.kinds = tuple(k for k in kinds if k in SOURCES)

    def _col(self):
        return self._db()[COLLECTION]

    async def _rows(self, kind: str, build_id: str):
        source = SOURCES[kind]
        async for raw in self._db()[source.collection].find(source.not_deleted, source.projection):
            doc = source.to_document(raw)
            if doc:
                yield to_catalog_document(doc, build_id)

    async def estimate_size_mb(self) -> float:
        """Approximate storage the catalog needs (rows + _id index). Read-only."""
        total = 0
        for kind in self.kinds:
            async for row in self._rows(kind, "estimate"):
                total += len(bson.encode(row)) + _ID_INDEX_BYTES_PER_DOC
        return total / 2**20

    async def cluster_usage_mb(self) -> float:
        """Data + index size across all databases (what Atlas shared tiers bill)."""
        client = self._db().client
        used = 0.0
        for name in await client.list_database_names():
            if name in ("admin", "local", "config"):
                continue
            stats = await client[name].command("dbStats")
            used += stats.get("dataSize", 0) + stats.get("indexSize", 0)
        return used / 2**20

    async def check_quota(self, limit_mb: float, safety_mb: float = 25.0) -> dict:
        """Raise StorageQuotaError if (re)building would leave < safety_mb free."""
        needed = await self.estimate_size_mb()
        used = await self.cluster_usage_mb()
        existing = 0.0
        if COLLECTION in await self._db().list_collection_names():
            stats = await self._db().command("collStats", COLLECTION)
            existing = (stats.get("size", 0) + stats.get("totalIndexSize", 0)) / 2**20
        projected = used - existing + needed
        report = {"used_mb": round(used), "catalog_mb": round(needed), "projected_mb": round(projected), "limit_mb": limit_mb}
        if projected > limit_mb - safety_mb:
            raise StorageQuotaError(
                f"catalog needs ~{needed:.0f} MB; cluster would use ~{projected:.0f} of "
                f"{limit_mb} MB (keeping {safety_mb:.0f} MB free). Free space or upgrade the tier."
            )
        return report

    async def rebuild(self) -> dict:
        """Re-index every searchable item; removes items that no longer exist."""
        build_id = uuid.uuid4().hex
        counts: dict[str, int] = {}

        for kind in self.kinds:
            counts[kind] = 0
            batch: list[ReplaceOne] = []
            async for row in self._rows(kind, build_id):
                batch.append(ReplaceOne({"_id": row["_id"]}, row, upsert=True))
                if len(batch) >= BATCH_SIZE:
                    await self._col().bulk_write(batch, ordered=False)
                    counts[kind] += len(batch)
                    batch = []
            if batch:
                await self._col().bulk_write(batch, ordered=False)
                counts[kind] += len(batch)

        removed = await self._col().delete_many({"build_id": {"$ne": build_id}})
        summary = {"indexed": counts, "removed": removed.deleted_count}
        logger.info("search catalog rebuilt: %s", summary)
        return summary

    async def refresh(self, kind: str, ref_id: str) -> None:
        """Re-index one item (or drop it if it was deleted)."""
        if kind not in self.kinds:
            return
        source = SOURCES[kind]
        raw = await self._db()[source.collection].find_one(
            {"_id": ref_id, **source.not_deleted}, source.projection
        )
        doc = source.to_document(raw) if raw else None
        if doc:
            row = to_catalog_document(doc)
            await self._col().replace_one({"_id": row["_id"]}, row, upsert=True)
        else:
            await self._col().delete_one({"_id": catalog_id(kind, ref_id)})

    async def index_status(self) -> dict | None:
        """Atlas Search index info ({'status', 'queryable', ...}) or None if absent."""
        if COLLECTION not in await self._db().list_collection_names():
            return None
        cursor = await self._col().list_search_indexes(INDEX_NAME)
        found = await cursor.to_list(None)
        return found[0] if found else None

    async def ensure_index(self) -> str:
        """Create the Atlas Search index if missing. Returns its status."""
        status = await self.index_status()
        if status is None:
            if COLLECTION not in await self._db().list_collection_names():
                await self._db().create_collection(COLLECTION)
            await self._col().create_search_index(
                SearchIndexModel(definition=INDEX_DEFINITION, name=INDEX_NAME)
            )
            return "CREATING"
        return status.get("status", "UNKNOWN")
