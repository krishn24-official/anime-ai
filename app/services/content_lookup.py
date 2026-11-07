"""LEGACY helper for modules not yet migrated to clean architecture.

New code should depend on the ContentCatalog port (app.domain.shared.ports) and get
it from app.container.content_catalog(). Delete this file once its callers migrate.
"""

from app.container import content_catalog
from app.domain.shared.content import ContentRef
from app.infrastructure.mongo.collections import (
    CONTENT_COLLECTIONS as CONTENT_COLLECTION_MAP,  # noqa: F401  (legacy re-export)
)


async def resolve_content_title(content_type: str, content_id: str) -> dict | None:
    """Returns {'title', 'poster_image'} for a catalog item, or None if not found."""
    ref = ContentRef(content_type, content_id)
    summary = (await content_catalog().get_summaries([ref])).get(ref)
    if not summary:
        return None
    return {"title": summary.title or content_id, "poster_image": summary.poster_image}
