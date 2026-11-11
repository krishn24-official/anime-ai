from typing import Protocol

from app.domain.recommendations.entities import BaseTitle, Recommendation


class RecommendationCatalog(Protocol):
    async def base_title(self, content_type: str, content_id: str) -> BaseTitle | None: ...

    async def link(self, recs: list[Recommendation]) -> list[Recommendation]:
        """The same recommendations, with content_id set for titles we store."""
        ...


class RecommendationSource(Protocol):
    async def similar(self, base: BaseTitle, limit: int) -> list[Recommendation]:
        """Titles people recommend to fans of `base` (adult titles excluded)."""
        ...
