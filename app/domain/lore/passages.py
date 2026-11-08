"""Turning episode pages into searchable passages. Pure Python, no I/O.

Built straight from the parsed page (the old pipeline rendered a PDF and read the
text back out, losing structure). Each passage carries its episode heading so a
retrieved passage always says which episode it is about.
"""

import re

from app.domain.lore.entities import EpisodePage, LorePassage

MAX_CHARS = 900  # fits all-MiniLM-L6-v2's 256-token window with the heading
OVERLAP_SENTENCES = 1
# Some wikis (Bleach) recap every punch: beyond this many passages an episode's extra
# detail costs more storage (Atlas free tier) than it adds to answers.
MAX_PASSAGES_PER_EPISODE = 10

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")


def split_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP_SENTENCES) -> list[str]:
    """Paragraph- and sentence-aware chunks of at most ~max_chars, overlapping by
    `overlap` sentences so an event split across chunks is still findable."""
    sentences = [s.strip() for p in text.split("\n") for s in _SENTENCE_END.split(p) if s.strip()]
    chunks, current = [], []
    for sentence in sentences:
        if current and len(" ".join(current + [sentence])) > max_chars:
            chunks.append(" ".join(current))
            current = current[-overlap:] if overlap else []
        while len(sentence) > max_chars:  # one huge "sentence": hard split
            chunks.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        current.append(sentence)
    if current:
        chunks.append(" ".join(current))
    return chunks


def character_id(name: str) -> str:
    return "char_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def episode_passages(series_id: str, series_title: str, page: EpisodePage) -> list[LorePassage]:
    if not page.summary:
        return []  # never index an empty page ("Detailed synopsis unavailable")
    heading = f"{series_title} Episode {page.number}" + (f": {page.title}" if page.title else "")
    facts = "; ".join(x for x in (
        f"Arc: {page.arc}" if page.arc else "",
        f"Adapts manga chapters: {page.chapters}" if page.chapters else "",
        "Filler episode" if page.filler else "",
    ) if x)
    characters = tuple(character_id(c) for c in page.characters)
    return [
        LorePassage(
            series_id=series_id,
            section_title=heading,
            text=f"[{heading}]\n" + (f"{facts}\n" if facts else "") + chunk,
            episode_number=page.number,
            character_ids=characters,
        )
        for chunk in split_text(page.summary)[:MAX_PASSAGES_PER_EPISODE]
    ]
