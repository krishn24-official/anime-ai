"""SearchIndex using MongoDB regular expressions on the source collections.

Works on any MongoDB (local dev, CI) with no extra setup. Slower than Atlas Search
on large collections, so it is the fallback when the Atlas index is unavailable.
"""

import asyncio
import re
from typing import Any, Callable

from app.domain.search import rules
from app.domain.search.entities import SearchDocument
from app.infrastructure.mongo.search_sources import SOURCES, SearchSource

_SEP = r"[\W_]*"  # optional punctuation/space between characters: spiderman ~ Spider-Man
# Start of a word. Not \b: MongoDB's \b is ASCII-only and never matches before
# Japanese/Cyrillic characters.
_WORD_START = r"(?<![A-Za-z0-9])"


def _chars_pattern(query: str, joiner: str) -> str | None:
    chars = rules.compact(query)
    if not chars:
        return None
    return joiner.join(re.escape(c) for c in chars)


def word_prefix_pattern(query: str) -> str | None:
    """Matches names where a word starts with the query, ignoring punctuation."""
    body = _chars_pattern(query, _SEP)
    return f"{_WORD_START}{body}" if body else None


def exact_pattern(query: str) -> str | None:
    body = _chars_pattern(query, _SEP)
    return rf"^\W*{body}\W*$" if body else None


def fuzzy_pattern(query: str) -> str | None:
    """Loose candidates for typo matching: characters in order, starting a word.
    The domain similarity threshold filters these afterwards."""
    body = _chars_pattern(query, ".*")
    return f"{_WORD_START}{body}" if body else None


class MongoRegexSearchIndex:
    def __init__(self, db_provider: Callable[[], Any]):
        self._db = db_provider

    async def candidates(
        self, query: str, kind: str, limit: int, fuzzy: bool
    ) -> list[SearchDocument]:
        source = SOURCES[kind]
        if fuzzy:
            patterns = [(fuzzy_pattern(query), limit)]
        else:
            # Exact matches are fetched separately so they are never crowded out
            # by many shorter partial matches.
            patterns = [(exact_pattern(query), 10), (word_prefix_pattern(query), limit)]

        batches = await asyncio.gather(
            *(self._find(source, p, n) for p, n in patterns if p)
        )
        seen: dict[str, SearchDocument] = {}
        for batch in batches:
            for doc in batch:
                seen.setdefault(doc.id, doc)
        return list(seen.values())

    async def _find(self, source: SearchSource, pattern: str, limit: int) -> list[SearchDocument]:
        regex = re.compile(pattern, re.IGNORECASE)
        match = {"$or": [{f: regex} for f in source.name_fields], **source.not_deleted}
        title_field = source.name_fields[0]
        pipeline = [
            {"$match": match},
            {"$addFields": {"_len": {"$strLenCP": {"$ifNull": [f"${title_field}", ""]}}}},
            {"$sort": {"_len": 1}},
            {"$limit": limit},
            {"$project": source.projection},
        ]
        cursor = await self._db()[source.collection].aggregate(pipeline)
        docs = [source.to_document(d) for d in await cursor.to_list(None)]
        return [d for d in docs if d]
