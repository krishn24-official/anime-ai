"""LEGACY: name filter pattern for the admin list endpoints (they filter with their
own queries because they include deleted items and review flags).

Uses the same matching as the search module: a word in the name starts with the
query, ignoring spaces and punctuation ("spiderman" matches "Spider-Man").
User input is escaped. Ranked search for everything else: app.application.search.
"""

from app.infrastructure.mongo.regex_search_index import word_prefix_pattern

_MATCH_NOTHING = "(?!)"


def build_fuzzy_search_regex(query: str) -> str:
    """Regex pattern (string) for MongoDB name filters. Name kept for existing callers."""
    return word_prefix_pattern(query or "") or _MATCH_NOTHING
