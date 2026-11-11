from typing import Protocol

from app.domain.lore.entities import EpisodePage, EpisodeRef, LorePassage


class EpisodeCatalog(Protocol):
    async def series_title(self, series_id: str) -> str: ...

    async def episodes(self, series_id: str) -> list[EpisodeRef]: ...

    async def save_pages(self, series_id: str, pages: list[EpisodePage]) -> int:
        """Store fetched titles/summaries on the episode records; returns how many changed."""
        ...


class EpisodePageSource(Protocol):
    async def fetch(self, series_id: str, episodes: list[EpisodeRef]) -> list[EpisodePage]:
        """Parsed wiki pages for the episodes that could be found."""
        ...


class TextEmbedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]] | None: ...


class LoreStore(Protocol):
    async def replace_series(self, series_id: str, passages: list[LorePassage], vectors: list[list[float]]) -> dict:
        """Back up and replace every passage of the series; returns stats (incl. backup path)."""
        ...
