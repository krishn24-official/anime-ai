"""MongoDB collection names. A storage detail, so it lives in infrastructure."""

# Content type (domain vocabulary) -> MongoDB collection holding it.
CONTENT_COLLECTIONS: dict[str, str] = {
    "anime": "anime",
    "manga": "manga",
    "movie": "movies",
    "tv_series": "tv_series",
}

TRENDING = "trending"
TRENDING_MENTIONS = "trending_mentions"
SEARCH_LOGS = "search_logs"
