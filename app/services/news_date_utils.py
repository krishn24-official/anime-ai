import time
from datetime import datetime, timezone

from dateutil import parser


def normalize_datetime(value):
    """Normalize timestamps, strings, and datetime objects to timezone-aware UTC."""
    if value is None:
        return None

    if isinstance(value, datetime):
        published = value
    elif isinstance(value, (int, float)):
        published = datetime.fromtimestamp(value, timezone.utc)
    elif isinstance(value, str):
        try:
            published = parser.parse(value)
        except Exception:
            return None
    else:
        return None

    if published is None:
        return None

    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    return published


def parse_published_entry(entry):
    """Extract a published datetime from RSS/Atom feedparser entries."""
    candidates = [
        getattr(entry, "published_parsed", None),
        getattr(entry, "updated_parsed", None),
    ]

    for candidate in candidates:
        if candidate:
            try:
                return datetime.fromtimestamp(time.mktime(candidate), timezone.utc)
            except Exception:
                pass

    for field in ["published", "updated", "created", "dc:date"]:
        value = getattr(entry, field, None)
        if value:
            normalized = normalize_datetime(value)
            if normalized:
                return normalized

    return None