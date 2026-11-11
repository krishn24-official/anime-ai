from dataclasses import replace
from datetime import datetime

from app.domain.shared.content import ContentRef, ContentSummary
from app.domain.trending.entities import MentionCount, SearchCount, TrendingEntry

_OPTIONAL = ("set_by", "note", "expires_at", "custom_poster")


class InMemoryTrendingRepository:
    def __init__(self):
        self.rows: dict[ContentRef, TrendingEntry] = {}

    async def get(self, content):
        return self.rows.get(content)

    async def save(self, entry):
        existing = self.rows.get(entry.content)
        if existing:  # same semantics as the Mongo repo: unset optionals are kept
            keep = {f: getattr(existing, f) for f in _OPTIONAL if not getattr(entry, f)}
            entry = replace(entry, **keep)
        self.rows[entry.content] = entry

    async def delete(self, content):
        self.rows.pop(content, None)

    async def list_active(self, now, limit):
        active = [e for e in self.rows.values() if not e.expires_at or e.expires_at > now]
        active.sort(key=lambda e: (e.pinned, e.score), reverse=True)
        return active[:limit]


class InMemorySignalRepository:
    def __init__(self, mentions=None, searches=None):
        self.mentions: set[tuple[ContentRef, str]] = set()
        self.mention_rows: list[tuple[ContentRef, datetime]] = []
        self.search_rows: list[tuple[ContentRef, str, datetime]] = []
        self.fixed_search_counts = searches  # optional canned result

    async def record_mention(self, content, news_id, matched_alias, at):
        if (content, news_id) in self.mentions:
            return
        self.mentions.add((content, news_id))
        self.mention_rows.append((content, at))

    async def mention_counts(self, since):
        counts: dict[ContentRef, int] = {}
        for ref, at in self.mention_rows:
            if at >= since:
                counts[ref] = counts.get(ref, 0) + 1
        return [MentionCount(ref, n) for ref, n in counts.items()]

    async def record_search_click(self, content, query, user_id, at):
        self.search_rows.append((content, user_id, at))

    async def search_counts(self, since):
        if self.fixed_search_counts is not None:
            return self.fixed_search_counts
        users: dict[ContentRef, set[str]] = {}
        for ref, user, at in self.search_rows:
            if at >= since:
                users.setdefault(ref, set()).add(user)
        return [SearchCount(ref, len(u)) for ref, u in users.items()]


class InMemoryCatalog:
    def __init__(self, items: dict[ContentRef, ContentSummary] | None = None):
        self.items = items or {}

    async def get_summaries(self, refs):
        return {r: self.items[r] for r in refs if r in self.items}


class FakeImageStorage:
    def __init__(self, url="https://img.example/poster.png"):
        self.url = url
        self.uploads: list[tuple[bytes, str]] = []

    async def upload(self, data, folder):
        self.uploads.append((data, folder))
        return self.url
