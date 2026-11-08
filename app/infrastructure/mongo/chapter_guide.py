"""ChapterGuide backed by the `chapters` and `episodes` collections (scraped wiki
data: titles, summaries, and which anime episodes adapt each chapter)."""

import re
from typing import Any, Callable

from app.domain.guide.entities import ChapterInfo, EpisodeInfo

CHAPTER_FIELDS = {
    "chapter_number": 1, "title": 1, "japanese_title": 1, "arc": 1,
    "short_summary": 1, "summary": 1, "long_summary": 1, "anime_adaptation": 1,
}
EPISODE_FIELDS = {"episode_number": 1, "title": 1, "summary": 1, "arc": 1, "is_filler": 1, "manga_chapters_covered": 1}
SUMMARY_CHARS = 700
_EPISODE = re.compile(r"\bEpisode (\d+)\b")
_GENERIC_TITLE = re.compile(r"^(?:Episode|Chapter) \d+$")
_IMAGE_CAPTION = re.compile(r"^\s*thumb\|[^\n]*\n?", re.M)  # "thumb|left|190px|[[caption]]" lines
_WIKI_LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")  # [[target|text]] -> text


def _slug(series_id: str) -> str:
    return series_id.split("_", 1)[1] if series_id.startswith(("anime_", "manga_")) else series_id


def _number(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _numbers(n: int) -> dict:
    """Numbers are stored as strings for some documents and ints for others."""
    return {"$in": [n, str(n)]}


def _clean(text: str | None) -> str:
    """Scraped wiki text without image captions and link markup."""
    return _WIKI_LINK.sub(lambda m: m.group(1), _IMAGE_CAPTION.sub("", text or "")).strip()


def _title(value) -> str | None:
    return value if value and not _GENERIC_TITLE.match(value) else None


def _chapter(doc: dict) -> ChapterInfo:
    summary = _clean(doc.get("short_summary") or doc.get("summary")) or _clean(doc.get("long_summary"))[:SUMMARY_CHARS]
    return ChapterInfo(
        number=_number(doc.get("chapter_number")) or 0,
        title=_title(doc.get("title")),
        summary=summary or None,
        arc=doc.get("arc") or None,
        japanese_title=doc.get("japanese_title") or None,
        anime_episodes=tuple(dict.fromkeys(int(n) for n in _EPISODE.findall(doc.get("anime_adaptation") or ""))),
    )


def _episode(doc: dict) -> EpisodeInfo:
    return EpisodeInfo(
        number=_number(doc.get("episode_number")) or 0,
        title=_title(doc.get("title")),
        summary=_clean(doc.get("summary"))[:SUMMARY_CHARS] or None,
        arc=doc.get("arc") or None,
        filler=bool(doc.get("is_filler")),
        chapters_covered=str(doc["manga_chapters_covered"]) if doc.get("manga_chapters_covered") else None,
    )


class MongoChapterGuide:
    def __init__(self, db_provider: Callable[[], Any]):
        self._db = db_provider
        self._manga_ids: dict[str, str | None] = {}

    async def _manga_id(self, series_id: str) -> str | None:
        """The manga holding this series' chapters: anime_naruto_shippuden -> manga_naruto."""
        if series_id not in self._manga_ids:
            parts = _slug(series_id).split("_")
            found = None
            for end in range(len(parts), 0, -1):  # longest name first
                candidate = "manga_" + "_".join(parts[:end])
                if await self._db()["chapters"].find_one({"manga_id": candidate}, {"_id": 1}):
                    found = candidate
                    break
            self._manga_ids[series_id] = found
        return self._manga_ids[series_id]

    def _anime_id(self, series_id: str) -> str:
        return "anime_" + _slug(series_id)

    async def series_title(self, series_id: str) -> str | None:
        manga_id = await self._manga_id(series_id)
        has_episodes = await self._db()["episodes"].find_one({"anime_id": self._anime_id(series_id)}, {"_id": 1})
        if not manga_id and not has_episodes:
            return None
        doc = manga_id and await self._db()["chapters"].find_one({"manga_id": manga_id, "series_title": {"$nin": [None, ""]}}, {"series_title": 1})
        return (doc or {}).get("series_title") or _slug(series_id).replace("_", " ").title()

    async def chapter(self, series_id: str, number: int) -> ChapterInfo | None:
        manga_id = await self._manga_id(series_id)
        doc = manga_id and await self._db()["chapters"].find_one(
            {"manga_id": manga_id, "chapter_number": _numbers(number)}, CHAPTER_FIELDS
        )
        return _chapter(doc) if doc else None

    async def episode(self, series_id: str, number: int) -> EpisodeInfo | None:
        doc = await self._db()["episodes"].find_one(
            {"anime_id": self._anime_id(series_id), "episode_number": _numbers(number), "is_deleted": {"$ne": True}},
            EPISODE_FIELDS,
        )
        return _episode(doc) if doc else None

    async def chapters_adapted_in(self, series_id: str, episode: int) -> list[ChapterInfo]:
        manga_id = await self._manga_id(series_id)
        if not manga_id:
            return []
        docs = await self._db()["chapters"].find(
            {"manga_id": manga_id, "anime_adaptation": {"$regex": rf"\bEpisode {episode}\b"}}, CHAPTER_FIELDS
        ).to_list(None)
        return sorted((_chapter(d) for d in docs), key=lambda c: c.number)

    def _matching(self, manga_id: str, patterns: list[str]) -> dict:
        return {"manga_id": manga_id, "$and": [{"long_summary": {"$regex": p, "$options": "i"}} for p in patterns]}

    async def earliest_mentioning(self, series_id: str, patterns: list[str], limit: int) -> list[ChapterInfo]:
        manga_id = await self._manga_id(series_id)
        if not manga_id:
            return []
        chapters = self._db()["chapters"]
        # Numbers are mixed str/int, so sort in Python: fetch just the numbers first.
        ids = await chapters.find(self._matching(manga_id, patterns), {"chapter_number": 1}).to_list(None)
        ids.sort(key=lambda d: _number(d.get("chapter_number")) or 10**9)
        docs = await chapters.find({"_id": {"$in": [d["_id"] for d in ids[:limit]]}}, CHAPTER_FIELDS).to_list(None)
        return sorted((_chapter(d) for d in docs), key=lambda c: c.number)

    async def most_mentioning(self, series_id: str, patterns: list[str], limit: int) -> list[ChapterInfo]:
        manga_id = await self._manga_id(series_id)
        if not manga_id:
            return []
        # Count matches in the database so only the winners' text is transferred.
        hits = {"$add": [
            {"$size": {"$regexFindAll": {"input": {"$ifNull": ["$long_summary", ""]}, "regex": p, "options": "i"}}}
            for p in patterns
        ]}
        cursor = await self._db()["chapters"].aggregate([
            {"$match": self._matching(manga_id, patterns)},
            {"$project": {**CHAPTER_FIELDS, "hits": hits}},
            {"$sort": {"hits": -1}},
            {"$limit": limit},
        ])
        results = []
        for doc in await cursor.to_list(None):
            info = _chapter(doc)
            results.append(ChapterInfo(**{**info.__dict__, "summary": _passage(_clean(doc.get("long_summary")), patterns)}))
        return results


def _passage(text: str, patterns: list[str], radius: int = SUMMARY_CHARS // 2) -> str:
    """The part of a summary around the first match of the rarest pattern."""
    found = [(len(re.findall(p, text, re.I)), m) for p in patterns if (m := re.search(p, text, re.I))]
    if not found:
        return text[:SUMMARY_CHARS]
    _, m = min(found, key=lambda pair: pair[0])
    start = max(0, m.start() - radius)
    return ("..." if start else "") + text[start:m.end() + radius].strip() + "..."
