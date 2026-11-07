"""Global search use case: one query across every searchable kind."""

import asyncio

from app.domain.search import rules
from app.domain.search.entities import (
    SEARCH_KINDS,
    RankedHit,
    SearchDocument,
    SearchResults,
)
from app.domain.search.ports import SearchIndex

# How many candidates to ask the index for per kind. The index may over-match;
# ranking with the domain rules decides what is shown.
CANDIDATES_PER_KIND = 50


class SearchService:
    def __init__(self, index: SearchIndex, kinds: tuple[str, ...] = SEARCH_KINDS):
        self._index = index
        self._kinds = kinds

    async def search(self, query: str) -> SearchResults:
        query = (query or "").strip()
        empty = SearchResults(by_kind={k: [] for k in self._kinds}, top=None)
        if len(rules.compact(query)) < rules.MIN_QUERY_LENGTH:
            return empty

        hits = await self._ranked_hits(query, fuzzy=False)

        has_strong = any(rules.is_strong(h.rank) for v in hits.values() for h in v)
        if has_strong:
            # Good matches exist: hide weak ones ("itachi" inside "Hitachi").
            hits = {k: [h for h in v if rules.is_strong(h.rank)] for k, v in hits.items()}
        elif rules.fuzzy_allowed(query):
            # Nothing good found: add typo-tolerant matches ("narto" -> "Naruto").
            fuzzy_hits = await self._ranked_hits(query, fuzzy=True)
            hits = {k: _merge(hits[k], fuzzy_hits[k]) for k in self._kinds}

        limit = rules.result_limit(query)
        by_kind = {k: sorted(hits[k], key=lambda h: h.sort_key)[:limit] for k in self._kinds}
        return SearchResults(by_kind=by_kind, top=_top_hit(by_kind, self._kinds))

    async def _ranked_hits(self, query: str, fuzzy: bool) -> dict[str, list[RankedHit]]:
        candidate_lists = await asyncio.gather(
            *(
                self._index.candidates(query, kind, CANDIDATES_PER_KIND, fuzzy)
                for kind in self._kinds
            )
        )
        return {
            kind: _rank(query, docs, allow_fuzzy=fuzzy)
            for kind, docs in zip(self._kinds, candidate_lists)
        }


def _rank(query: str, docs: list[SearchDocument], allow_fuzzy: bool) -> list[RankedHit]:
    hits = []
    for doc in docs:
        rank = rules.match_rank(query, doc, allow_fuzzy=allow_fuzzy)
        if rank is not None:
            hits.append(RankedHit(doc, rank))
    return hits


def _merge(first: list[RankedHit], second: list[RankedHit]) -> list[RankedHit]:
    best: dict[str, RankedHit] = {}
    for hit in first + second:
        current = best.get(hit.document.id)
        if current is None or hit.sort_key < current.sort_key:
            best[hit.document.id] = hit
    return list(best.values())


def _top_hit(by_kind: dict[str, list[RankedHit]], kinds: tuple[str, ...]) -> RankedHit | None:
    """Best match overall across kinds.

    Lowest rank wins; on a tie, the title closest to the query (shortest), then the
    earlier kind in `kinds`. Popularity is not compared: it is measured differently
    per kind (votes vs. none).
    """
    leaders = [
        (hits[0].rank, len(hits[0].document.title), i, hits[0])
        for i, k in enumerate(kinds)
        if (hits := by_kind[k])
    ]
    return min(leaders, key=lambda t: t[:3])[3] if leaders else None
