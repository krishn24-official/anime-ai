"""Spotting the same story reported by several sources. Pure Python, no I/O.

Sources word headlines differently ("Druski Dons Whiteface as Elizabeth Holmes..."
vs "Druski Does Elizabeth Holmes Whiteface In..."), so exact matching fails.
Two headlines are the same story when most of their *distinctive* words match,
or (when headline embeddings are available) when their meanings are very close,
e.g. "Emma Stone Joins Druski During His SNL Hosting Debut" vs "Emma Stone Crashes
Druski's SNL Monologue". Embeddings are optional: without them the word rule runs alone.

Errs on the side of keeping articles: a missed duplicate is a small annoyance,
a hidden story is lost news. So:
  - generic news words ("trailer", "season", "announced") are ignored, otherwise
    "One Piece Season 2 Trailer" would match "Bleach Season 2 Trailer";
  - a review / interview / episode post only matches the same kind of post,
    otherwise "Dragon's Dogma 2 Review" would match a Dragon's Dogma 2 news item;
  - only different sources are compared (one site does not repeat its own story,
    but does reuse headline templates), and YouTube videos are never merged.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

MIN_SHARED = 3  # distinctive words both headlines must contain
MIN_OVERLAP = 0.6  # shared words / words in the shorter headline
# Cosine similarity of normalised headline embeddings (all-MiniLM-L6-v2) above which
# two headlines are the same story. Tuned on two weeks of real news: lower values
# start merging different updates about one title (e.g. day-1 vs day-2 box office).
MIN_SIMILARITY = 0.72
# ...and only for articles published this close together: coverage of one event lands
# within hours, while look-alike follow-ups ("advance booking" vs "day 2") come days apart.
SIMILARITY_WINDOW = timedelta(hours=24)
NEVER_MERGED_SOURCES = frozenset({"youtube"})  # each video is its own item

STOPWORDS = frozenset("""
a an the and or but of in on at to for from by with as into over after before about
is are was were be been being it its this that these those his her their our your
my we you they he she i me him them who what when where why how than then so not no
can could will would should may might must do does did done has have had just also
up out off new first last more most all any some one two three vs via amid during
says said say reveals revealed reveal shares share shows show gets get got make makes
official officially announced announces announce confirms confirmed report reports
reportedly exclusive watch watching video videos photo photos look
trailer trailers teaser teasers clip clips poster posters season seasons part
release released releases releasing date dates premiere premieres
update updates news latest breaking full live here now
anime manga film films movie movies series tv game games
cast casts staff visual visuals key main additional opening ending theme themes song songs
""".split())

# Words that mark a kind of post rather than a story.
KIND_MARKERS = frozenset({"review", "reviews", "interview", "episode", "episodes", "recap", "preview", "previews"})

_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Headline:
    words: frozenset[str]  # distinctive, normalised words
    kind: frozenset[str]  # e.g. {"review"}; empty for ordinary news
    vector: tuple[float, ...] | None = None  # normalised embedding, if available
    published_at: datetime | None = None


def parse_headline(title: str, vector=None, published_at: datetime | None = None) -> Headline:
    text = unicodedata.normalize("NFKC", title).lower().replace("’", "'")
    text = re.sub(r"'s\b", "", text)
    words, kind = set(), set()
    for w in _WORD.findall(text):
        if w in KIND_MARKERS:
            kind.add(w.rstrip("s"))
            continue
        if w in STOPWORDS or (w.isdigit() and len(w) < 4):  # keep years, drop "2"
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]  # crude plural folding
        words.add(w)
    return Headline(frozenset(words), frozenset(kind), tuple(vector) if vector else None, _naive_utc(published_at))


def _naive_utc(dt: datetime | None) -> datetime | None:
    """Mongo hands back naive UTC datetimes while freshly fetched articles are
    timezone-aware; normalise both to naive UTC so they can be subtracted."""
    if dt is None or dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def similarity(a: Headline, b: Headline) -> float | None:
    if a.vector is None or b.vector is None:
        return None
    return sum(x * y for x, y in zip(a.vector, b.vector))


def same_story(a: Headline, b: Headline) -> bool:
    if a.kind != b.kind:
        return False
    shared = len(a.words & b.words)
    if shared == 0:  # the same story always shares at least a name
        return False
    shorter = min(len(a.words), len(b.words))
    if shared >= MIN_SHARED and shared / shorter >= MIN_OVERLAP:
        return True
    if a.published_at is None or b.published_at is None or abs(a.published_at - b.published_at) > SIMILARITY_WINDOW:
        return False
    score = similarity(a, b)
    return score is not None and score >= MIN_SIMILARITY


def can_merge(source: str | None) -> bool:
    return (source or "") not in NEVER_MERGED_SOURCES


def find_original(
    headline: Headline, source: str | None, recent: list[tuple[object, str | None, Headline]]
) -> object | None:
    """Id of the first recent article (oldest first) from another source telling
    the same story, if any. `recent` holds (id, source, headline) tuples."""
    if not can_merge(source):
        return None
    for article_id, other_source, other in recent:
        if other_source != source and can_merge(other_source) and same_story(headline, other):
            return article_id
    return None
