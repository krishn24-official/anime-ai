import logging
import time

from app.domain.search.entities import SearchDocument
from app.domain.search.ports import SearchIndex, SearchIndexUnavailable

logger = logging.getLogger(__name__)
LOG_EVERY_SECONDS = 300


class FallbackSearchIndex:
    """Uses `primary` and falls back to `fallback` whenever primary fails
    (e.g. the Atlas index is not built yet, or MongoDB is not on Atlas)."""

    def __init__(self, primary: SearchIndex, fallback: SearchIndex):
        self._primary = primary
        self._fallback = fallback
        self._last_logged = 0.0

    async def candidates(
        self, query: str, kind: str, limit: int, fuzzy: bool
    ) -> list[SearchDocument]:
        try:
            return await self._primary.candidates(query, kind, limit, fuzzy)
        except SearchIndexUnavailable as exc:
            # Expected (index not built yet, kind not indexed): not worth a warning.
            logger.debug("primary search index unavailable: %s", exc)
            return await self._fallback.candidates(query, kind, limit, fuzzy)
        except Exception as exc:
            if time.monotonic() - self._last_logged > LOG_EVERY_SECONDS:
                logger.warning("primary search index unavailable, using fallback: %s", exc)
                self._last_logged = time.monotonic()
            return await self._fallback.candidates(query, kind, limit, fuzzy)
