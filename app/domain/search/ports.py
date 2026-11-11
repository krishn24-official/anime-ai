from typing import Protocol

from app.domain.search.entities import SearchDocument


class SearchIndexUnavailable(Exception):
    """The index cannot serve queries right now (e.g. not built yet)."""


class SearchIndex(Protocol):
    async def candidates(
        self, query: str, kind: str, limit: int, fuzzy: bool
    ) -> list[SearchDocument]:
        """Documents of `kind` that may match `query` (a superset is fine:
        the application ranks and filters them with domain rules).

        fuzzy=True asks for typo-tolerant candidates as well.
        Raises SearchIndexUnavailable if the index cannot be used.
        """
        ...
