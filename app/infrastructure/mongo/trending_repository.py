from datetime import datetime
from typing import Any, Callable

from pymongo.errors import DuplicateKeyError

from app.domain.shared.content import ContentRef
from app.domain.trending.entities import MentionCount, SearchCount, TrendingEntry
from app.infrastructure.mongo import collections

_OPTIONAL_FIELDS = ("set_by", "note", "expires_at", "custom_poster")


def _key(content: ContentRef) -> dict:
    return {"content_type": content.content_type, "content_id": content.content_id}


def _to_entry(doc: dict) -> TrendingEntry:
    return TrendingEntry(
        content=ContentRef(doc["content_type"], doc["content_id"]),
        source=doc.get("source", ""),
        reason=doc.get("reason", ""),
        score=float(doc.get("score", 0.0)),
        pinned=bool(doc.get("pinned", False)),
        computed_at=doc.get("computed_at"),
        set_by=doc.get("set_by"),
        note=doc.get("note"),
        expires_at=doc.get("expires_at"),
        custom_poster=doc.get("custom_poster"),
    )


class MongoTrendingRepository:
    """TrendingRepository backed by the `trending` collection."""

    def __init__(self, db_provider: Callable[[], Any]):
        self._db = db_provider

    def _col(self):
        return self._db()[collections.TRENDING]

    async def get(self, content: ContentRef) -> TrendingEntry | None:
        doc = await self._col().find_one(_key(content))
        return _to_entry(doc) if doc else None

    async def save(self, entry: TrendingEntry) -> None:
        fields = {
            **_key(entry.content),
            "source": entry.source,
            "reason": entry.reason,
            "score": entry.score,
            "pinned": entry.pinned,
            "computed_at": entry.computed_at,
        }
        for name in _OPTIONAL_FIELDS:
            value = getattr(entry, name)
            if value:  # unset optional fields keep their stored value
                fields[name] = value

        await self._col().update_one(_key(entry.content), {"$set": fields}, upsert=True)

    async def delete(self, content: ContentRef) -> None:
        await self._col().delete_one(_key(content))

    async def list_active(self, now: datetime, limit: int) -> list[TrendingEntry]:
        # The TTL index removes expired docs eventually, but not instantly, so filter too.
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"expires_at": {"$exists": False}},
                        {"expires_at": None},
                        {"expires_at": {"$gt": now}},
                    ]
                }
            },
            {"$sort": {"pinned": -1, "score": -1}},
            {"$limit": limit},
        ]
        cursor = await self._col().aggregate(pipeline)
        return [_to_entry(doc) for doc in await cursor.to_list(None)]


class MongoTrendingSignalRepository:
    """TrendingSignalRepository backed by `trending_mentions` and `search_logs`."""

    def __init__(self, db_provider: Callable[[], Any]):
        self._db = db_provider

    async def record_mention(
        self, content: ContentRef, news_id: str, matched_alias: str, at: datetime
    ) -> None:
        try:
            await self._db()[collections.TRENDING_MENTIONS].insert_one(
                {
                    **_key(content),
                    "news_id": news_id,
                    "matched_alias": matched_alias,
                    "matched_at": at,
                }
            )
        except DuplicateKeyError:
            pass  # unique index on (content_id, news_id): already recorded

    async def mention_counts(self, since: datetime) -> list[MentionCount]:
        pipeline = [
            {"$match": {"matched_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {"content_type": "$content_type", "content_id": "$content_id"},
                    "count": {"$sum": 1},
                }
            },
        ]
        cursor = await self._db()[collections.TRENDING_MENTIONS].aggregate(pipeline)
        return [
            MentionCount(
                ContentRef(d["_id"]["content_type"], d["_id"]["content_id"]), d["count"]
            )
            for d in await cursor.to_list(None)
        ]

    async def record_search_click(
        self, content: ContentRef, query: str, user_id: str, at: datetime
    ) -> None:
        await self._db()[collections.SEARCH_LOGS].insert_one(
            {**_key(content), "query": query, "user_id": user_id, "searched_at": at}
        )

    async def search_counts(self, since: datetime) -> list[SearchCount]:
        pipeline = [
            {"$match": {"searched_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {"content_type": "$content_type", "content_id": "$content_id"},
                    "users": {"$addToSet": "$user_id"},
                }
            },
            {"$project": {"count": {"$size": "$users"}}},
        ]
        cursor = await self._db()[collections.SEARCH_LOGS].aggregate(pipeline)
        return [
            SearchCount(
                ContentRef(d["_id"]["content_type"], d["_id"]["content_id"]), d["count"]
            )
            for d in await cursor.to_list(None)
        ]
