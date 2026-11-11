"""Understanding episode / chapter questions. Pure Python, no I/O.

Vector search over lore cannot answer "what's the first chapter called?" or
"in which episode does Luffy first use Gear 5?": the first needs a lookup by
number, the second the *earliest* chapter mentioning a term. This turns a question
into those lookups.
"""

import re
from dataclasses import dataclass, field

ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_NUMBER_NAMES = {n: [w for w, v in {**ORDINALS, **NUMBER_WORDS}.items() if v == n] for n in range(1, 11)}

STOPWORDS = frozenset("""
a an the and or of in on at to for from by with as is are was were be been did does do
what which who whom when where why how name named called title titled tell me about
episode episodes chapter chapters ep ch manga anime first time times used use uses
using happen happened happens appear appears appeared appearance debut debuts
show shows showed get gets got start starts started begin begins began
""".split())

# "first time", "first used", "first appearance", "debut": the earliest mention.
# Not a bare "first" ("who is the first Hokage?" is not about when something happened).
_FIRST = re.compile(
    r"\b(?:first\s+(?:time|use[ds]?|using|appear(?:s|ed|ance)?|show(?:s|ed|n)?|met|meets?|seen)|debut(?:s|ed)?|earliest)\b",
    re.I,
)
_TERM = re.compile(r"[a-z][a-z'\-]*(?:\s+\d+)?|\d+", re.I)


@dataclass(frozen=True)
class GuideQuestion:
    chapter: int | None = None  # "chapter 12", "first chapter"
    episode: int | None = None  # "episode 5", "first episode"
    earliest: bool = False  # "first time", "debut": the earliest chapter mentioning the terms
    terms: tuple[str, ...] = field(default_factory=tuple)  # e.g. ("luffy", "gear 5")

    @property
    def is_empty(self) -> bool:
        return self.chapter is None and self.episode is None and not self.terms


def _number_of(unit: str, text: str) -> int | None:
    """'chapter 12' / 'ch. 12' / 'first chapter' / 'chapter one' -> 12 / 12 / 1 / 1."""
    short = {"chapter": "ch", "episode": "ep"}[unit]
    m = re.search(rf"\b(?:{unit}|{short}\.?)\s*#?\s*(\d+)\b", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(rf"\b({'|'.join(ORDINALS)})\s+{unit}\b", text, re.I)
    if m:
        return ORDINALS[m.group(1).lower()]
    m = re.search(rf"\b{unit}\s+({'|'.join(NUMBER_WORDS)})\b", text, re.I)
    return NUMBER_WORDS[m.group(1).lower()] if m else None


def parse_guide_question(text: str, ignore: tuple[str, ...] = ()) -> GuideQuestion:
    """`ignore`: words of the series title, which say nothing about the event."""
    chapter = _number_of("chapter", text)
    episode = _number_of("episode", text)
    ignored = STOPWORDS | {w.lower() for w in ignore}
    # The chapter/episode number itself is not a term.
    cleaned = re.sub(r"\b(?:chapter|episode|ch|ep)\.?\s*#?\s*\d+\b", " ", text, flags=re.I)
    terms = []
    for raw in _TERM.findall(cleaned.lower()):
        word, _, number = raw.partition(" ")
        word = word.removesuffix("'s")  # "what's", "luffy's"
        if word in ignored or word in ORDINALS or word in NUMBER_WORDS or len(word) < 3:
            continue
        terms.append(f"{word} {number}" if number else word)
    return GuideQuestion(
        chapter=chapter,
        episode=episode,
        earliest=bool(_FIRST.search(text)),
        terms=tuple(dict.fromkeys(terms)),
    )


def is_exact_question(text: str) -> bool:
    """A chapter/episode number, or "first time" + something: the guide answers it
    precisely, so it should be looked up rather than left to the model's judgment."""
    q = parse_guide_question(text)
    return q.chapter is not None or q.episode is not None or (q.earliest and bool(q.terms))


def term_pattern(term: str) -> str:
    """Regex for a term in summaries: "gear 5" also matches "Gear Fifth" / "Gear Five"."""
    word, _, number = term.partition(" ")
    if not number:
        return rf"\b{re.escape(word)}"
    names = [number] + _NUMBER_NAMES.get(int(number), [])
    return rf"\b{re.escape(word)}\s*(?:{'|'.join(names)})\b"
