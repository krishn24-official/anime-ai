# Maps known sources/channels directly to a category. All current sources
# are mapped, so the news pipeline runs without any AI/Gemini calls.
# Add new entries here when new sources/channels are introduced.

SOURCE_CATEGORY_MAP = {
    "animecorner": "Anime",
    "animenewsnetwork": "Anime",
    "crunchyroll": "Anime",
    "myanimelist": "Anime",
    "boxoffice": "Movies",
    "pinkvilla": "Movies",
    "filmfare": "Movies",
    "bollywood_hungama": "Movies",
    "koimoi": "Movies",
    "variety": "Movies",
    "thr": "Movies",
    "slashfilm": "Movies",
}

# YouTube channel name -> category. Channels not listed here are
# unmapped and will be skipped by the pipeline (skipped_unmapped) until
# added here.
YOUTUBE_CHANNEL_CATEGORY_MAP = {
    # Games
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
    # Anime
    "Shonen Jump": "Anime",
    "Kodansha": "Anime",
    "VIZ Media": "Anime",
    "Aniplex USA": "Anime",
    "Toei Animation": "Anime",
    "Crunchyroll": "Anime",
    "Netflix Anime": "Anime",
    "Muse Asia": "Anime",
    "Ani-One Asia": "Anime",
    # Movies
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


TV_KEYWORDS = (
    "season ",
    "episode ",
    "series",
    "tv show",
    "web series",
    "docuseries",
    "miniseries",
    "limited series",
    "sitcom",
    "k-drama",
    "drama series",
    "spinoff series",
    "ott release",
)


def get_mapped_category(article: dict) -> str | None:
    """
    Return a category for the article based on its source/channel, or
    None if the source/channel isn't mapped yet (pipeline will skip it).
    """
    source = article.get("source")

    if source == "youtube":
        channel = article.get("youtube_channel")
        cat = YOUTUBE_CHANNEL_CATEGORY_MAP.get(channel)
    else:
        cat = SOURCE_CATEGORY_MAP.get(source)

    if cat == "Movies":
        title_lower = (article.get("title") or "").lower()
        if any(kw in title_lower for kw in TV_KEYWORDS):
            return "TV Series"

    return cat


def smart_truncate(text: str, max_length: int = 500) -> str:
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    # cut at the last complete sentence if one exists within range
    last_period = truncated.rfind(". ")
    if last_period > max_length * 0.5:  # only use it if it's not too far back
        return truncated[: last_period + 1]
    # otherwise cut at the last whole word
    last_space = truncated.rfind(" ")
    return truncated[:last_space] + "..." if last_space > 0 else truncated + "..."


def make_fallback_summary(article: dict) -> str:
    """Summary for source-mapped articles: RSS description, truncated."""
    description = (article.get("description") or "").strip()

    if description:
        return smart_truncate(description, 240)

    return smart_truncate((article.get("title") or ""), 240)
