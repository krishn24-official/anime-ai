from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.shared.content import ContentRef


class TrendingSource(str, Enum):
    MANUAL = "manual"  # pinned by an admin ("Editor's Pick")
    NEWS = "news"  # mentioned in recent news articles
    SEARCH = "search"  # searched by many distinct users


@dataclass
class TrendingEntry:
    """One item on the trending list, as stored."""

    content: ContentRef
    source: str
    reason: str
    score: float
    pinned: bool
    computed_at: datetime
    set_by: str | None = None
    note: str | None = None
    expires_at: datetime | None = None
    custom_poster: str | None = None


@dataclass(frozen=True)
class TrendingItem:
    """A trending entry enriched with display data (what clients receive)."""

    content_type: str
    content_id: str
    title: str
    poster_image: str | None
    reason: str | None
    pinned: bool
    set_at: datetime | None
    note: str | None


@dataclass(frozen=True)
class MentionCount:
    content: ContentRef
    mention_count: int


@dataclass(frozen=True)
class SearchCount:
    content: ContentRef
    distinct_searcher_count: int
