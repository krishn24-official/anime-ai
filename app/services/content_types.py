from bson import ObjectId
from bson.errors import InvalidId

VALID_CONTENT_TYPES = {"anime", "manga", "movie", "tv_series"}

CONTENT_COLLECTION_MAP = {
    "anime": "anime",
    "manga": "manga",
    "movie": "movies",
    "tv_series": "tv_series",
}


def is_valid_content_type(content_type: str) -> bool:
    return content_type in VALID_CONTENT_TYPES


def to_object_id(value: str) -> ObjectId | None:
    """Used for ObjectId-based ids (users, comments) -- NOT content_id,
    since content collections (anime, manga, etc.) use custom string ids
    like 'anime_naruto'."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None