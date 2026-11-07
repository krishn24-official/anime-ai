"""LEGACY re-exports for modules not yet migrated to clean architecture.

New code should import from:
  - app.domain.shared.content            (content types, validation)
  - app.infrastructure.mongo.collections  (MongoDB collection names)
Delete this file once the content module is migrated.
"""

from bson import ObjectId
from bson.errors import InvalidId

from app.domain.shared.content import CONTENT_TYPES as VALID_CONTENT_TYPES
from app.domain.shared.content import is_valid_content_type
from app.infrastructure.mongo.collections import (
    CONTENT_COLLECTIONS as CONTENT_COLLECTION_MAP,
)

__all__ = [
    "VALID_CONTENT_TYPES",
    "CONTENT_COLLECTION_MAP",
    "is_valid_content_type",
    "to_object_id",
]


def to_object_id(value: str) -> ObjectId | None:
    """Used for ObjectId-based ids (users, comments) -- NOT content_id,
    since content collections (anime, manga, etc.) use custom string ids
    like 'anime_naruto'."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None
