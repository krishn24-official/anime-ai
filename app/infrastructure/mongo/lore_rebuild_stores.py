"""EpisodeCatalog and LoreStore backed by MongoDB (`episodes`, `anime`, `lore_chunks`)."""

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from bson import json_util
from bson.binary import Binary, BinaryVectorDtype
from pymongo import UpdateOne

from app.domain.lore.entities import EpisodePage, EpisodeRef, LorePassage
from app.infrastructure.mongo.content_catalog import summary_from_document

SOURCE = "fandom-wiki"  # lore_chunks.source_file of rebuilt passages
INSERT_BATCH = 500
_GENERIC_TITLE = re.compile(r"^\s*episode\s*\d+\s*$", re.I)


def _number(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class MongoEpisodeCatalog:
    def __init__(self, db_provider: Callable[[], Any]):
        self._db = db_provider

    async def series_title(self, series_id: str) -> str:
        doc = await self._db()["anime"].find_one({"_id": series_id}, {"title": 1, "name": 1})
        return (summary_from_document(doc).title if doc else None) or series_id.split("_", 1)[-1].replace("_", " ").title()

    async def episodes(self, series_id: str) -> list[EpisodeRef]:
        docs = await self._db()["episodes"].find(
            {"anime_id": series_id, "is_deleted": {"$ne": True}}, {"episode_number": 1, "wiki_page": 1, "title": 1}
        ).to_list(None)
        refs = {}
        for d in docs:  # duplicates (two id schemes) collapse onto one episode number
            n = _number(d.get("episode_number"))
            if n is None:
                continue
            title = d.get("title") if d.get("title") and not _GENERIC_TITLE.match(d["title"]) else None
            prev = refs.get(n)
            refs[n] = EpisodeRef(n, d.get("wiki_page") or (prev.page if prev else None), title or (prev.title if prev else None))
        return [refs[n] for n in sorted(refs)]

    async def save_pages(self, series_id: str, pages: list[EpisodePage]) -> int:
        ops = []
        for p in pages:
            fields = {"summary": p.summary} if p.summary else {}
            if p.title:
                fields["title"] = p.title
            if p.arc:
                fields["arc"] = p.arc
            if p.chapters:
                fields["manga_chapters_covered"] = p.chapters
            if fields:
                fields["updated_at"] = datetime.now(timezone.utc)
                ops.append(UpdateOne(
                    {"anime_id": series_id, "episode_number": {"$in": [p.number, str(p.number)]}},
                    {"$set": fields},
                ))
        if not ops:
            return 0
        result = await self._db()["episodes"].bulk_write(ops, ordered=False)
        return result.modified_count


class MongoLoreStore:
    def __init__(self, db_provider: Callable[[], Any], backup_dir: str = "backups"):
        self._db = db_provider
        self._backup_dir = backup_dir

    async def replace_series(self, series_id: str, passages: list[LorePassage], vectors: list[list[float]]) -> dict:
        chunks = self._db()["lore_chunks"]
        old = await chunks.find({"series_id": series_id}).to_list(None)
        os.makedirs(self._backup_dir, exist_ok=True)
        backup = os.path.join(self._backup_dir, f"lore_{series_id}_{datetime.now():%Y%m%d_%H%M%S}.json")
        with open(backup, "w", encoding="utf-8") as fh:  # written before anything is deleted
            fh.write(json_util.dumps(old))

        now = datetime.now(timezone.utc)
        docs = []
        for p, vector in zip(passages, vectors):
            chunk_id = str(uuid.uuid4())
            docs.append({
                "_id": chunk_id,
                "chunk_id": chunk_id,
                "series_id": series_id,
                "character_ids": list(p.character_ids),
                # float32 binary vector: ~1.5 KB instead of ~4.9 KB as an array of doubles
                "embedding_vector": Binary.from_vector(list(vector), BinaryVectorDtype.FLOAT32),
                "source_file": SOURCE,
                "section_title": p.section_title,
                "chunk_text": p.text,
                "episode_number": p.episode_number,
                "created_at": now,
            })
        deleted = (await chunks.delete_many({"series_id": series_id})).deleted_count
        for i in range(0, len(docs), INSERT_BATCH):
            await chunks.insert_many(docs[i:i + INSERT_BATCH], ordered=False)
        return {"backup": backup, "old_passages": deleted, "new_passages": len(docs)}
