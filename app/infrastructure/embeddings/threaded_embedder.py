"""HeadlineEmbedder over any blocking `texts -> vectors` function (e.g. sentence-transformers)."""

import asyncio
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class ThreadedEmbedder:
    def __init__(self, encode: Callable[[list[str]], list[list[float]]]):
        self._encode = encode

    async def embed(self, texts: list[str]) -> list[list[float]] | None:
        if not texts:
            return []
        try:
            # CPU-bound: keep it off the event loop.
            return await asyncio.to_thread(self._encode, texts)
        except Exception as e:  # missing model, out of memory, ...: callers fall back
            logger.warning("embedding failed, continuing without it: %s", e)
            return None
