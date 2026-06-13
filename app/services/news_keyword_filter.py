# Entertainment-related keyword filter used to drop irrelevant articles
# before sending them to Gemini for categorization/summarization.

KEYWORDS = [
    "trailer", "official trailer", "teaser", "poster", "first look",
    "motion poster", "release date", "worldwide release",
    "movie", "film", "sequel", "part 2", "spin-off", "remake",
    "cast", "starring", "joins the cast", "directed by",
    "marvel", "dc", "avengers", "spider-man", "batman", "superman",
    "anime", "manga", "netflix", "ott", "season", "episode",
    "box office", "collection", "anime news", "voice actor",
]


def is_relevant(title: str, description: str = "") -> bool:
    """Basic relevance check: keep if title/description matches any keyword,
    or if it came from a known entertainment-specific source (caller decides)."""
    text = f"{title} {description}".lower()
    return any(keyword in text for keyword in KEYWORDS)


def filter_news(articles):
    return list(articles) if articles is not None else []