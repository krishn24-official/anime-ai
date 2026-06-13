# Maps known sources/channels directly to a category. All current sources
# are mapped, so the news pipeline runs without any AI/Gemini calls.
# Add new entries here when new sources/channels are introduced.

SOURCE_CATEGORY_MAP = {
    "animecorner": "Anime",
    "animenewsnetwork": "Anime",
    "crunchyroll": "Anime",
    "myanimelist": "Anime",

    "boxoffice": "Movies",
    "screenrant": "Movies",
    "entertainment_news": "Movies",
}

# YouTube channel name -> category. Channels not listed here are
# unmapped and will be skipped by the pipeline (skipped_unmapped) until
# added here.
YOUTUBE_CHANNEL_CATEGORY_MAP = {
    "IGN": "Games",
    "GameSpot": "Games",
    "PlayStation": "Games",
    "Xbox": "Games",
    "Nintendo": "Games",

    "Shonen Jump": "Anime",
    "Aniplex USA": "Anime",
    "Toei Animation": "Anime",
    "Crunchyroll": "Anime",

    # Netflix/Marvel/DC post a mix of movie and TV-series content;
    # default to "Movies" for now. Split into separate categories
    # (e.g. "Marvel", "Netflix") later if desired -- just update this
    # map and VALID_CATEGORIES in news_repository.py.
    "Netflix": "Movies",
    "Marvel": "Movies",
    "DC": "Movies",
}


def get_mapped_category(article: dict) -> str | None:
    """
    Return a category for the article based on its source/channel, or
    None if the source/channel isn't mapped yet (pipeline will skip it).
    """
    source = article.get("source")

    if source == "youtube":
        channel = article.get("youtube_channel")
        return YOUTUBE_CHANNEL_CATEGORY_MAP.get(channel)

    return SOURCE_CATEGORY_MAP.get(source)


def make_fallback_summary(article: dict) -> str:
    """Summary for source-mapped articles: RSS description, truncated."""
    description = (article.get("description") or "").strip()

    if description:
        return description[:240]

    return (article.get("title") or "")[:240]