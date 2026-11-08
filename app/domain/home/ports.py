"""Where hero slides come from. Implemented in infrastructure."""

from datetime import date, datetime
from typing import Protocol

from app.domain.home.entities import HeroSlide


class HeroSource(Protocol):
    """Each method returns slides that have an image, best first."""

    async def editor_picks(self, now: datetime, limit: int) -> list[HeroSlide]: ...

    async def latest_trailers(self, since: datetime, limit: int) -> list[HeroSlide]:
        """Titles with a trailer published since `since` (that trailer is shown), most popular first."""
        ...

    async def upcoming_releases(self, start: date, end: date, limit: int) -> list[HeroSlide]:
        """Titles releasing between start and end (inclusive), most popular first."""
        ...

    async def latest_news(self, since: datetime, limit: int) -> list[HeroSlide]: ...
