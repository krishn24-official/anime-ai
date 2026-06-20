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


def extract_image_url(entry) -> str | None:
    """Extract a thumbnail or content image URL from a feedparser entry."""
    # 1. Check media_thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")
    
    # 2. Check media_content
    if hasattr(entry, "media_content") and entry.media_content:
        return entry.media_content[0].get("url")
        
    # 3. Check enclosures (often contains image attachments)
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enclosure in entry.enclosures:
            if enclosure.get("type", "").startswith("image/"):
                return enclosure.get("url")
                
    # 4. Check links
    if hasattr(entry, "links") and entry.links:
        for link in entry.links:
            if link.get("type", "").startswith("image/"):
                return link.get("href")
                
    return None