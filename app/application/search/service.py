"""Search use cases. Every search in the app goes through here, so results are
ranked the same way everywhere:

- search():      the global search bar (a few results per kind + top result)
- search_kind(): one kind, paginated (Library lists, pickers, per-type endpoints)
"""

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
# Upper bound on ranked results a paginated listing can page through.
MAX_LISTING_RESULTS = 200


class SearchService:
    def __init__(self, index: SearchIndex, kinds: tuple[str, ...] = SEARCH_KINDS):
        self._index = index
        self._kinds = kinds

    async def search(self, query: str) -> SearchResults:
        query = (query or "").strip()
        if not _searchable(query):
            return SearchResults(by_kind={k: [] for k in self._kinds}, top=None)

        hits = await self._ranked(query, self._kinds, CANDIDATES_PER_KIND)
        limit = rules.result_limit(query)
        by_kind = {k: hits[k][:limit] for k in self._kinds}
        return SearchResults(by_kind=by_kind, top=_top_hit(by_kind, self._kinds))

    async def search_kind(
        self, query: str, kind: str, limit: int, offset: int = 0
    ) -> tuple[list[SearchDocument], int]:
        """Best matches of one kind, best first. Returns (page, total matches).

        total is capped at MAX_LISTING_RESULTS.
        """
        query = (query or "").strip()
        if kind not in self._kinds or not _searchable(query):
            return [], 0
        hits = (await self._ranked(query, (kind,), MAX_LISTING_RESULTS))[kind]
        return [h.document for h in hits[offset : offset + limit]], len(hits)

    async def _ranked(
        self, query: str, kinds: tuple[str, ...], candidates: int
    ) -> dict[str, list[RankedHit]]:
        """Ranked hits per kind, applying the strong/weak/typo policy across kinds."""
        hits = await self._hits(query, kinds, candidates, fuzzy=False)

        if any(rules.is_strong(h.rank) for v in hits.values() for h in v):
            # Good matches exist: hide weak ones ("itachi" inside "Hitachi").
            hits = {k: [h for h in v if rules.is_strong(h.rank)] for k, v in hits.items()}
        elif rules.fuzzy_allowed(query):
            # Nothing good found: add typo-tolerant matches ("narto" -> "Naruto").
            fuzzy_hits = await self._hits(query, kinds, candidates, fuzzy=True)
            hits = {k: _merge(hits[k], fuzzy_hits[k]) for k in kinds}

        return {k: sorted(v, key=lambda h: h.sort_key) for k, v in hits.items()}

    async def _hits(
        self, query: str, kinds: tuple[str, ...], candidates: int, fuzzy: bool
    ) -> dict[str, list[RankedHit]]:
        candidate_lists = await asyncio.gather(
            *(self._index.candidates(query, kind, candidates, fuzzy) for kind in kinds)
        )
        return {
            kind: _rank(query, docs, allow_fuzzy=fuzzy)
            for kind, docs in zip(kinds, candidate_lists)
        }


def _searchable(query: str) -> bool:
    return len(rules.compact(query)) >= rules.MIN_QUERY_LENGTH


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
