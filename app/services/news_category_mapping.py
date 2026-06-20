# Maps known sources/channels directly to a category. All current sources
# are mapped, so the news pipeline runs without any AI/Gemini calls.
# Add new entries here when new sources/channels are introduced.

SOURCE_CATEGORY_MAP = {
    "animecorner": "Anime",
    "animenewsnetwork": "Anime",
    "crunchyroll": "Anime",
    "myanimelist": "Anime",

    "boxoffice": "Movies",
}

# YouTube channel name -> category. Channels not listed here are
# unmapped and will be skipped by the pipeline (skipped_unmapped) until
# added here.
YOUTUBE_CHANNEL_CATEGORY_MAP = {
    # 🎮 Games
    "IGN": "Games",
    "GameSpot": "Games",
    "PlayStation": "Games",
    "Xbox": "Games",
    "Nintendo": "Games",
    "Eurogamer": "Games",
    "PC Gamer": "Games",
    "Bandai Namco": "Games",
    "Ubisoft": "Games",
    "Square Enix": "Games",
    "Capcom": "Games",
    "Epic Games": "Games",
    "SEGA": "Games",

    # 📚 Anime
    "Shonen Jump": "Anime",
    "Kodansha": "Anime",
    "VIZ Media": "Anime",
    "Aniplex USA": "Anime",
    "Toei Animation": "Anime",
    "Crunchyroll": "Anime",
    "Netflix Anime": "Anime",
    "Muse Asia": "Anime",
    "Ani-One Asia": "Anime",

    # 🎬 Movies
    "Netflix": "Movies",
    "Prime Video": "Movies",
    "Disney+": "Movies",
    "Apple TV+": "Movies",
    "HBO": "Movies",
    "Marvel": "Movies",
    "DC": "Movies",
    "Warner Bros": "Movies",
    "Sony Pictures": "Movies",
    "Universal Pictures": "Movies",
    "Paramount Pictures": "Movies",
    "Lionsgate": "Movies",
    "20th Century Studios": "Movies",
    "A24": "Movies",
    "Rotten Tomatoes Trailers": "Movies",
    "T-Series": "Movies",
    "Yash Raj Films": "Movies",
    "Hombale Films": "Movies",
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