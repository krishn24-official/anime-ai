"""What news de-duplication needs from the outside world."""

from typing import Protocol


class HeadlineEmbedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Normalised embeddings, one per text; None if embedding is unavailable."""
        ...
