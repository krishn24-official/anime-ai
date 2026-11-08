"""Home page use cases."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.domain.home.entities import HeroSlide, SlideKind
from app.domain.home.ports import HeroSource
from app.domain.home.rules import mix_slides

logger = logging.getLogger(__name__)

FRESH_HOURS = 48  # trailers and news older than this are not "new"
RELEASE_DAYS = 14
PER_KIND = 4


class HomeService:
    def __init__(
        self,
        source: HeroSource,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        cache_ttl: timedelta = timedelta(minutes=10),
    ):
        self._source = source
        self._clock = clock
        self._ttl = cache_ttl
        self._cache: tuple[datetime, list[HeroSlide]] | None = None

    async def hero_feed(self, limit: int = 7) -> list[HeroSlide]:
        """Admin picks, new trailers, news and upcoming releases, interleaved.

        Cached briefly: the same feed is shown to every visitor.
        """
        now = self._clock()
        if self._cache and now - self._cache[0] < self._ttl:
            return self._cache[1][:limit]

        kinds = (SlideKind.PICK, SlideKind.TRAILER, SlideKind.NEWS, SlideKind.RELEASE)
        results = await asyncio.gather(
            self._source.editor_picks(now, PER_KIND),
            self._source.latest_trailers(now - timedelta(hours=FRESH_HOURS), PER_KIND),
            self._source.latest_news(now - timedelta(hours=FRESH_HOURS), PER_KIND),
            self._source.upcoming_releases(now.date(), (now + timedelta(days=RELEASE_DAYS)).date(), PER_KIND),
            return_exceptions=True,
        )
        groups = {}
        for kind, result in zip(kinds, results):
            if isinstance(result, Exception):  # one broken source must not empty the hero
                logger.warning("hero source %s failed: %s", kind.value, result)
                result = []
            groups[kind] = result

        slides = mix_slides(groups, limit=len(kinds) * PER_KIND)
        self._cache = (now, slides)
        return slides[:limit]
