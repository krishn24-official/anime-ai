"""Rebuild a series' lore (the RAG vector index) from its episode wiki pages."""

from app.domain.lore.entities import RebuildReport
from app.domain.lore.passages import episode_passages
from app.domain.lore.ports import EpisodeCatalog, EpisodePageSource, LoreStore, TextEmbedder


class LoreRebuildService:
    def __init__(self, catalog: EpisodeCatalog, source: EpisodePageSource, embedder: TextEmbedder, store: LoreStore):
        self._catalog = catalog
        self._source = source
        self._embedder = embedder
        self._store = store

    async def rebuild(self, series_id: str, apply: bool = False, limit: int | None = None) -> RebuildReport:
        """Fetch -> parse -> passages -> embeddings -> replace. With apply=False nothing is
        written (pages are still fetched and parsed, so the report shows what would change)."""
        title = await self._catalog.series_title(series_id)
        episodes = await self._catalog.episodes(series_id)
        if limit:
            episodes = episodes[:limit]
        pages = await self._source.fetch(series_id, episodes)
        passages = [p for page in pages for p in episode_passages(series_id, title, page)]

        report = dict(
            series_id=series_id,
            episodes=len(episodes),
            pages_found=len(pages),
            with_story=sum(1 for p in pages if p.summary),
            passages=len(passages),
            sample=passages[:3],
        )
        if not apply:
            return RebuildReport(**report, applied=False)
        if not passages:
            raise RuntimeError(f"No passages built for {series_id}: refusing to replace its lore with nothing")

        vectors = await self._embedder.embed([p.text for p in passages])
        if not vectors or len(vectors) != len(passages):
            raise RuntimeError("Embedding failed: lore left unchanged")
        stats = {"episodes_updated": await self._catalog.save_pages(series_id, pages)}
        stats.update(await self._store.replace_series(series_id, passages, vectors))
        return RebuildReport(**report, applied=True, store_stats=stats)
