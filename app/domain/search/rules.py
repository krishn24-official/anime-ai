"""Pure search relevance rules. No I/O.

A result is ranked by *how* the query matches its title or one of its aliases
(best first):

    1. exact                       "naruto"  -> "Naruto"
    2. starts with whole words     "goku"    -> "Goku Son"
    3. contains whole words        "titan"   -> "Attack on Titan"
    4. starts with                 "goku"    -> "Gokujo."
    5. a word starts with          "piec"    -> "One Piece"
    6. contains (weak)             "itachi"  -> "Hitachi"
    7. typo (weak)                 "narto"   -> "Naruto"

Spaces and punctuation are ignored when the query ends on a whole word, so
"spiderman" and "spider man" both match "Spider-Man" (but "aot" does not match
"Ao to ..."). A title match beats an alias match of the same level, but an exact
alias ("AoT") beats any partial title match. Weak matches are shown only when
there is no strong one. Ties: RankedHit.sort_key.
"""

import unicodedata
from difflib import SequenceMatcher
from enum import IntEnum

from app.domain.search.entities import SearchDocument

MIN_QUERY_LENGTH = 2  # compact characters
SHORT_QUERY_LENGTH = 2  # queries this short only get a few, very close matches
SHORT_QUERY_LIMIT = 3
DEFAULT_LIMIT = 5
FUZZY_MIN_LENGTH = 4  # typo matching only for queries at least this long
FUZZY_MIN_SIMILARITY = 0.85


class MatchLevel(IntEnum):
    EXACT = 0
    PREFIX_WORDS = 1
    WORDS = 2
    PREFIX = 3
    WORD_PREFIX = 4
    CONTAINS = 5
    FUZZY = 6


STRONG_LEVELS = MatchLevel.WORD_PREFIX


def rank_of(level: MatchLevel, is_alias: bool) -> int:
    """Final rank: lower is better. Title beats alias at the same level."""
    return int(level) * 2 + int(is_alias)


def is_strong(rank: int) -> bool:
    return rank // 2 <= STRONG_LEVELS


def normalize(text: str) -> str:
    """Lowercase, strip accents, turn punctuation into spaces, collapse spaces.

    "Spider-Man: No Way Home" -> "spider man no way home"; "Pokémon" -> "pokemon".
    Letters of any script are kept, so Japanese/Cyrillic aliases still match.
    """
    decomposed = unicodedata.normalize("NFKD", text or "")
    chars = []
    for ch in decomposed:
        if unicodedata.combining(ch):
            continue
        chars.append(ch.lower() if ch.isalnum() else " ")
    return " ".join("".join(chars).split())


def compact(text: str) -> str:
    """normalize() without spaces: "Spider-Man" -> "spiderman"."""
    return normalize(text).replace(" ", "")


def result_limit(query: str) -> int:
    return SHORT_QUERY_LIMIT if len(compact(query)) <= SHORT_QUERY_LENGTH else DEFAULT_LIMIT


def fuzzy_allowed(query: str) -> bool:
    return len(compact(query)) >= FUZZY_MIN_LENGTH


def _whole_words_at(qc: str, words: list[str], i: int) -> bool:
    """Do words[i], words[i+1], ... spell exactly qc (spaces ignored)?"""
    consumed = 0
    for w in words[i:]:
        consumed += len(w)
        if consumed >= len(qc):
            return consumed == len(qc) and "".join(words[i:]).startswith(qc)
    return False


def _word_level(q: str, qc: str, words: list[str]) -> MatchLevel | None:
    """Best level for the query starting at a word boundary.

    Whole-word matches ignore spaces ("spiderman" ~ "spider man"); partial ones
    must match as typed, so "aot" does not match "ao to midori".
    """
    if _whole_words_at(qc, words, 0):
        return MatchLevel.PREFIX_WORDS
    if any(_whole_words_at(qc, words, i) for i in range(1, len(words))):
        return MatchLevel.WORDS
    n = " ".join(words)
    if n.startswith(q):
        return MatchLevel.PREFIX
    if (" " + n).find(" " + q) > 0:
        return MatchLevel.WORD_PREFIX
    return None


def _is_typo_of(qc: str, words: list[str]) -> bool:
    """Similar to a word, two adjacent words, or the start of the name.
    Typos rarely change the first letter, so that must match."""
    joined = "".join(words)
    options = set(words)
    options.update(a + b for a, b in zip(words, words[1:]))
    options.add(joined[: len(qc) + 1])
    return any(
        o[:1] == qc[:1] and SequenceMatcher(None, qc, o).ratio() >= FUZZY_MIN_SIMILARITY
        for o in options
        if o
    )


def _level_for_name(q: str, qc: str, name: str, allow_fuzzy: bool) -> MatchLevel | None:
    n = normalize(name)
    if not n:
        return None
    words = n.split()
    if n == q or "".join(words) == qc:
        return MatchLevel.EXACT
    level = _word_level(q, qc, words)
    if level is not None:
        return level
    if q in n:
        return MatchLevel.CONTAINS
    if allow_fuzzy and _is_typo_of(qc, words):
        return MatchLevel.FUZZY
    return None


def match_rank(query: str, document: SearchDocument, allow_fuzzy: bool = False) -> int | None:
    """How well the document matches the query (lower is better), or None."""
    q, qc = normalize(query), compact(query)
    if len(qc) < MIN_QUERY_LENGTH:
        return None

    best = None
    names = [(document.title, False)] + [(alias, True) for alias in document.aliases]
    for name, is_alias in names:
        level = _level_for_name(q, qc, name, allow_fuzzy)
        if level is not None:
            rank = rank_of(level, is_alias)
            best = rank if best is None else min(best, rank)
    return best
