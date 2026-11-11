"""Storage interfaces the trending use cases need. Implemented in infrastructure."""

from datetime import datetime
from typing import Protocol

from app.domain.shared.content import ContentRef
from app.domain.trending.entities import MentionCount, SearchCount, TrendingEntry


class TrendingRepository(Protocol):
    async def get(self, content: ContentRef) -> TrendingEntry | None: ...

    async def save(self, entry: TrendingEntry) -> None:
        """Insert or update the entry for entry.content.

        Optional fields that are None are left unchanged on an existing entry.
        """
        ...

    async def delete(self, content: ContentRef) -> None: ...

    async def list_active(self, now: datetime, limit: int) -> list[TrendingEntry]:
        """Entries not expired at `now`, pinned first, then by score (highest first)."""
        ...


class TrendingSignalRepository(Protocol):
    """Raw signals that automatic trending is computed from."""

    async def record_mention(
        self, content: ContentRef, news_id: str, matched_alias: str, at: datetime
    ) -> None:
        """Record that a news article mentions content. Repeats for the same
        (content, article) pair are ignored."""
        ...

    async def mention_counts(self, since: datetime) -> list[MentionCount]: ...

    async def record_search_click(
        self, content: ContentRef, query: str, user_id: str, at: datetime
    ) -> None: ...

    async def search_counts(self, since: datetime) -> list[SearchCount]: ...
