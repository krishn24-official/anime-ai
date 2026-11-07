"""Keeps the search catalog in step with admin edits.

Decorate an admin route that creates, updates or deletes a searchable item:

    @router.patch("/anime/{content_id}")
    @keeps_search_in_sync("anime")
    async def update_existing_anime(content_id: str, ...): ...

After the route succeeds, the item is re-indexed (the id comes from the
`content_id` path parameter or the response's "content_id"). Sync failures are
logged and never fail the request; the periodic rebuild repairs any gap.
"""

import functools
import logging

from app import container

logger = logging.getLogger(__name__)


def keeps_search_in_sync(kind: str):
    def decorator(endpoint):
        @functools.wraps(endpoint)  # FastAPI reads the original signature via __wrapped__
        async def wrapper(*args, **kwargs):
            result = await endpoint(*args, **kwargs)
            content_id = kwargs.get("content_id")
            if not content_id and isinstance(result, dict):
                content_id = result.get("content_id")
            if content_id and container.search_catalog_enabled():
                try:
                    await container.search_catalog().refresh(kind, content_id)
                except Exception as exc:
                    logger.warning("search sync failed for %s %s: %s", kind, content_id, exc)
            return result

        return wrapper

    return decorator
