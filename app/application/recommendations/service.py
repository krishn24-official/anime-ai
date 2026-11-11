"""'If you liked X, try...' use case."""

import logging

from app.application.search.service import SearchService
from app.domain.recommendations import rules
from app.domain.recommendations.entities import SimilarTitles
from app.domain.recommendations.ports import RecommendationCatalog, RecommendationSource
from app.domain.search.entities import CONTENT_TYPE_BY_KIND

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(
        self,
        search: SearchService,
        catalog: RecommendationCatalog,
        sources: dict[str, RecommendationSource],  # content type -> source
    ):
        self._search = search
        self._catalog = catalog
        self._sources = sources

    async def similar_to(self, query: str, limit: int = 6) -> SimilarTitles | None:
        """Titles similar to the one named in `query`; None if no such title is stored."""
        results = await self._search.search(query)
        hits = ([results.top] if results.top else []) + [h for hs in results.by_kind.values() for h in hs]
        hit = next((h for h in hits if CONTENT_TYPE_BY_KIND.get(h.document.kind) in self._sources), None)
        if hit is None:
            return None

        content_type = CONTENT_TYPE_BY_KIND[hit.document.kind]
        base = await self._catalog.base_title(content_type, hit.document.id)
        if base is None:
            return None
        try:
            recs = await self._sources[content_type].similar(base, limit * 2)
        except Exception as e:  # external API down: say "none found" rather than fail the chat
            logger.warning("recommendations for %s failed: %s", base.content_id, e)
            recs = []
        return SimilarTitles(base, await self._catalog.link(rules.pick(recs, base, limit)))
