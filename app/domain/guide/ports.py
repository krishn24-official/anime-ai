from typing import Protocol

from app.domain.guide.entities import ChapterInfo, EpisodeInfo


class ChapterGuide(Protocol):
    """Chapter and episode data of a series. `series_id` is the anime or manga id
    (e.g. "anime_one_piece"); implementations map it to the right collection."""

    async def series_title(self, series_id: str) -> str | None:
        """None when the series has neither chapters nor episodes on record."""
        ...

    async def chapter(self, series_id: str, number: int) -> ChapterInfo | None: ...

    async def episode(self, series_id: str, number: int) -> EpisodeInfo | None: ...

    async def chapters_adapted_in(self, series_id: str, episode: int) -> list[ChapterInfo]: ...

    async def earliest_mentioning(self, series_id: str, patterns: list[str], limit: int) -> list[ChapterInfo]:
        """Chapters whose summary matches every regex in `patterns`, lowest number first."""
        ...

    async def most_mentioning(self, series_id: str, patterns: list[str], limit: int) -> list[ChapterInfo]:
        """Chapters matching every pattern, most matches first; `summary` is the passage
        around the first match (keyword retrieval, complementing vector search)."""
        ...
