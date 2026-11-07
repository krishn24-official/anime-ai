"""Pure business rules for trending. No I/O."""

from app.domain.trending.entities import SearchCount, TrendingEntry

# Admin pins always rank above automatic entries.
EDITOR_PICK_REASON = "Editor's Pick"
EDITOR_PICK_SCORE = 1000.0

# Search trending: an item qualifies when its distinct-searcher count is at least
# MIN_SEARCH_THRESHOLD and at least RELATIVE_MULTIPLIER x the average.
MIN_SEARCH_THRESHOLD = 15
RELATIVE_MULTIPLIER = 2.0

# Folder used for custom trending posters in image storage.
TRENDING_IMAGE_FOLDER = "entertainment_hub/trending"


def may_replace(existing: TrendingEntry | None, incoming: TrendingEntry) -> bool:
    """Automatic (non-pinned) entries never overwrite an admin pin."""
    if incoming.pinned:
        return True
    return not (existing and existing.pinned)


def news_reason(count: int) -> str:
    return f"Mentioned in {count} article{'s' if count != 1 else ''} this week"


def search_reason(count: int) -> str:
    return f"Searched by {count} people recently"


def search_qualifying_threshold(counts: list[SearchCount]) -> float:
    if not counts:
        return MIN_SEARCH_THRESHOLD
    average = sum(c.distinct_searcher_count for c in counts) / len(counts)
    return max(MIN_SEARCH_THRESHOLD, average * RELATIVE_MULTIPLIER)
