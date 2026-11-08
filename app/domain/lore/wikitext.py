"""Reading fandom (MediaWiki) episode pages. Pure Python, no I/O.

Each wiki names things differently: the story is under "Long Summary" (One Piece),
"Plot" (Demon Slayer), "Plot Details" (Jujutsu Kaisen), "Synopsis" (Naruto) or
"Summary" (Bleach); the title is "Translation", "title", "ep title" or "english".
The old parser only knew "Synopsis|Summary|Plot", so most One Piece episodes were
stored as "Detailed synopsis unavailable".
"""

import re

from app.domain.lore.entities import EpisodePage

# Story sections, richest first; the longest non-empty one among the first group found wins.
STORY_SECTIONS = ("long summary", "plot details", "plot", "synopsis", "summary", "overview", "short summary")
TITLE_KEYS = ("translation", "title", "ep title", "episode title", "english", "name")
ARC_KEYS = ("arc", "story arc")
CHAPTER_KEYS = ("chapters", "manga chapters", "manga chapter", "adapted from")
FILLER_KEYS = ("filler", "is_filler")
MIN_STORY_CHARS = 80  # shorter "summaries" are stubs ("Coming soon", a single line)

_SECTION = re.compile(r"^(==+)\s*([^=\n]+?)\s*\1\s*$", re.M)
_INFOBOX_FIELD = re.compile(r"^\|\s*([^=|\n]+?)\s*=\s*(.*)$", re.M)
_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")


def clean_wikitext(text: str) -> str:
    """Wiki markup -> plain text."""
    t = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    t = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"\[\[(?:File|Image):(?:[^\[\]]|\[\[[^\]]*\]\])*\]\]", "", t, flags=re.I)  # images + captions
    t = re.sub(r"^\s*thumb\|.*$", "", t, flags=re.M)
    for _ in range(3):  # templates can nest
        t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = _LINK.sub(lambda m: m.group(2) or m.group(1), t)
    t = re.sub(r"\[https?://\S+\s+([^\]]+)\]", lambda m: m.group(1), t)  # [url label] -> label
    t = re.sub(r"'{2,}", "", t)  # bold/italic
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"^[*#:;]+\s*", "", t, flags=re.M)  # list markers
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _infobox(wikitext: str) -> dict[str, str]:
    fields = {}
    for key, value in _INFOBOX_FIELD.findall(wikitext.split("\n==", 1)[0]):
        fields.setdefault(key.strip().lower(), value.strip())
    return fields


def _sections(wikitext: str) -> dict[str, str]:
    """Top-level-ish sections by lower-cased heading, each with its own text."""
    found, matches = {}, list(_SECTION.finditer(wikitext))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(wikitext)
        found.setdefault(m.group(2).strip().lower(), wikitext[m.end():end])
    return found


def is_episode_page(wikitext: str) -> bool:
    """Wikis reuse names ("Homecoming" is a Naruto chapter and an episode): check the infobox."""
    templates = [t.lower() for t in re.findall(r"\{\{\s*(?:Template:)?([^|}\n]+)", wikitext[:3000])]
    if any("chapter" in t and "episode" not in t for t in templates[:3]):
        return False
    keys = set(_infobox(wikitext))
    return any("episode" in t for t in templates) or bool(
        keys & {"#", "episode", "ep number", "episodenumber", "number (overall)", "air_date", "jp air date", "japair"}
    )


def parse_episode_page(wikitext: str, number: int) -> EpisodePage | None:
    """None when the page is not an episode page."""
    if not wikitext or not is_episode_page(wikitext):
        return None
    box = _infobox(wikitext)
    sections = _sections(wikitext)

    raw_story = ""
    for name in STORY_SECTIONS:
        if clean_wikitext(sections.get(name, "")):
            candidates = [sections[n] for n in STORY_SECTIONS if n in sections]
            raw_story = max(candidates, key=lambda s: len(clean_wikitext(s)))
            break
    story = clean_wikitext(raw_story)
    if len(story) < MIN_STORY_CHARS:
        story = ""

    characters = tuple(dict.fromkeys(
        (m.group(1).strip() for m in _LINK.finditer(raw_story)
         if not re.match(r"(?:category|file|image|help|wikipedia|template):", m.group(1), re.I))
    ))[:25]

    def first(keys):
        return next((clean_wikitext(box[k]) for k in keys if clean_wikitext(box.get(k, ""))), None)

    title = first(TITLE_KEYS)
    if title and re.fullmatch(r"episode\s*\d+", title, re.I):
        title = None
    filler = (box.get(next((k for k in FILLER_KEYS if k in box), ""), "") or "").lower() in ("yes", "true", "1")
    return EpisodePage(
        number=number,
        title=title,
        summary=story,
        arc=first(ARC_KEYS),
        chapters=first(CHAPTER_KEYS),
        filler=filler,
        characters=characters,
    )
