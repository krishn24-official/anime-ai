"""Ports (interfaces) for capabilities shared by several modules.

Infrastructure provides the implementations; application code depends only on these.
"""

from typing import Protocol

from app.domain.shared.content import ContentRef, ContentSummary


class ContentCatalog(Protocol):
    """Read access to catalog items (anime, manga, movies, TV series)."""

    async def get_summaries(
        self, refs: list[ContentRef]
    ) -> dict[ContentRef, ContentSummary]:
        """Return summaries for the refs that exist; missing items are omitted."""
        ...


class ImageStorage(Protocol):
    """Stores uploaded images and returns a public URL."""

    async def upload(self, data: bytes, folder: str) -> str | None: ...
