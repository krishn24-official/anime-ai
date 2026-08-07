"""
Title Matcher Service
Builds an in-memory index of content titles and aliases to scan news text for mentions.
At current scale (few thousand titles, few dozen articles per run), a straightforward
regex scan is sufficient. If title counts grow significantly, this is the place to
swap in an Aho-Corasick multi-pattern matcher.
"""
import re
from app.db.mongo import get_db

MIN_ALIAS_LENGTH = 4
IGNORED_ALIASES = {
    "that", "this", "time", "when", "some", "what", "where", "your", "with",
    "will", "have", "they", "from", "more", "about"
}

def normalize_alias(text: str) -> str:
    """Lowercase, strip, and collapse internal whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    return re.sub(r'\s+', ' ', text)

async def build_alias_index() -> list[tuple[str, str, str]]:
    """
    Builds a list of (normalized_alias, content_type, content_id) tuples.
    Sorted by alias length descending.
    """
    db = get_db()
    aliases = []
    seen = set()

    def add_alias(alias: str, ctype: str, cid: str):
        if not isinstance(alias, str):
            return
        norm = normalize_alias(alias)
        if len(norm) >= MIN_ALIAS_LENGTH and norm not in IGNORED_ALIASES:
            tup = (norm, ctype, cid)
            if tup not in seen:
                seen.add(tup)
                aliases.append(tup)

    # Anime
    async for doc in db["anime"].find({}, {"_id": 1, "title": 1}):
        cid = str(doc["_id"])
        title = doc.get("title", {})
        if isinstance(title, dict):
            add_alias(title.get("english", ""), "anime", cid)
            add_alias(title.get("romaji", ""), "anime", cid)
            for syn in title.get("synonyms", []):
                add_alias(syn, "anime", cid)
        elif isinstance(title, str):
            add_alias(title, "anime", cid)

    # Manga
    async for doc in db["manga"].find({}, {"_id": 1, "name": 1}):
        add_alias(doc.get("name", ""), "manga", str(doc["_id"]))

    # Movies
    async for doc in db["movies"].find({}, {"_id": 1, "title": 1, "original_title": 1}):
        cid = str(doc["_id"])
        add_alias(doc.get("title", ""), "movie", cid)
        add_alias(doc.get("original_title", ""), "movie", cid)

    # TV Series
    async for doc in db["tv_series"].find({}, {"_id": 1, "title": 1, "original_title": 1}):
        cid = str(doc["_id"])
        add_alias(doc.get("title", ""), "tv_series", cid)
        add_alias(doc.get("original_title", ""), "tv_series", cid)

    # Sort longest first
    aliases.sort(key=lambda x: len(x[0]), reverse=True)
    return aliases

def find_matches(text: str, alias_index: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """
    Scans text for aliases using word-boundary regex.
    Deduplicates to avoid matching shorter substrings if a longer alias for the SAME content_id already matched.
    """
    if not text:
        return []
    
    norm_text = normalize_alias(text)
    matches = []
    seen_content_ids = set()

    for alias, ctype, cid in alias_index:
        if cid in seen_content_ids:
            continue
            
        if alias in norm_text:
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, norm_text):
                matches.append((alias, ctype, cid))
                seen_content_ids.add(cid)

    return matches
