"""Shared content vocabulary used across modules (trending, ratings, watchlist, ...)."""

from dataclasses import dataclass

# The kinds of catalog content the platform knows about.
CONTENT_TYPES: frozenset[str] = frozenset({"anime", "manga", "movie", "tv_series"})


def is_valid_content_type(content_type: str) -> bool:
    return content_type in CONTENT_TYPES


def content_types_label() -> str:
    """Stable, human-readable list for error messages."""
    return ", ".join(sorted(CONTENT_TYPES))


@dataclass(frozen=True)
class ContentRef:
    """Identifies one catalog item, e.g. ContentRef("anime", "anime_naruto")."""

    content_type: str
    content_id: str


@dataclass(frozen=True)
class ContentSummary:
    """Minimal display data for a catalog item."""

    title: str | None
    poster_image: str | None
