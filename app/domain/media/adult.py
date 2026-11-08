"""What counts as adult (18+) content. Pure Python, no I/O.

TMDb's own `adult` flag misses most softcore, pink films and JAV-adjacent titles, so
TMDb keyword tags are used too. A few famous arthouse/mainstream films carry the
same tags (Antichrist, Emmanuelle, ...), so titles with many votes are kept.
AniList's `isAdult` flag (explicit sexual content) is used for anime and manga.
"""

# TMDb keyword ids that mark adult releases.
ADULT_TMDB_KEYWORDS: dict[int, str] = {
    155477: "softcore",
    382870: "gay softcore",
    190370: "erotic movie",
    365656: "erotic moive",
    159551: "pink film",
    381597: "pinku eiga",
    198385: "hentai",
    384581: "hentai adaptation",
    330293: "jav",
    356830: "gay jav",
    342167: "japanese adult video (jav)",
    284535: "adult video",
    323931: "gravure idol",
}

# A tagged title with at least this many TMDb votes is a well-known film, kept.
MAINSTREAM_MIN_VOTES = 100

REMOVED_REASON = "adult_content"


def adult_keyword_names(keyword_ids) -> list[str]:
    return [ADULT_TMDB_KEYWORDS[k] for k in keyword_ids if k in ADULT_TMDB_KEYWORDS]


def is_adult_tmdb(flagged_adult: bool, keyword_ids, vote_count) -> bool:
    """True for TMDb titles that must not be stored."""
    if flagged_adult:
        return True
    return bool(adult_keyword_names(keyword_ids)) and (vote_count or 0) < MAINSTREAM_MIN_VOTES


def tmdb_keyword_ids(details: dict) -> list[int]:
    """Keyword ids from a TMDb details payload (movies: keywords.keywords, TV: keywords.results)."""
    kw = details.get("keywords") or {}
    return [k.get("id") for k in (kw.get("keywords") or kw.get("results") or []) if isinstance(k, dict)]
