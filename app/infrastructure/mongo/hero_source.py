"""HeroSource backed by MongoDB (trending pins, TMDb titles, news)."""

from datetime import date, datetime
from typing import Any, Callable

from app.domain.home.entities import HeroSlide, SlideKind
from app.domain.shared.content import ContentRef
from app.infrastructure.mongo.collections import CONTENT_COLLECTIONS, TRENDING
from app.infrastructure.mongo.content_catalog import summary_from_document

TMDB_KINDS = ("movie", "tv_series")
RELEASE_FIELD = {"movie": "release_date", "tv_series": "first_air_date"}
LIVE = {"is_deleted": {"$ne": True}, "is_adult": {"$ne": True}}
TITLE_FIELDS = {
    "title": 1, "name": 1, "images": 1, "plot": 1, "description": 1,
    "trailers": 1, "popularity": 1, "release_date": 1, "first_air_date": 1,
}


def _image(doc: dict) -> tuple[str | None, bool]:
    """(url, is_wide): a backdrop/banner if there is one, else the largest poster."""
    images = doc.get("images") if isinstance(doc.get("images"), dict) else {}
    wide = images.get("backdrop") or images.get("banner")
    if wide:
        return wide, True
    poster = images.get("poster")
    if poster and "anilist.co" in poster:
        poster = poster.replace("/cover/medium/", "/cover/large/")  # AniList: large/ = extraLarge
    return poster, False


def _title_slide(kind: SlideKind, content_type: str, doc: dict, **extra) -> HeroSlide | None:
    title = summary_from_document(doc).title
    image, wide = _image(doc)
    if not image and extra.get("fallback_image"):
        image, wide = extra["fallback_image"], False
    extra.pop("fallback_image", None)
    if not (title and image):
        return None
    return HeroSlide(
        kind=kind,
        key=f"{kind.value}:{doc['_id']}",
        title=title,
        image=image,
        image_is_wide=wide,
        description=doc.get("plot") or doc.get("description"),
        content=ContentRef(content_type, doc["_id"]),
        **extra,
    )


class MongoHeroSource:
    def __init__(self, db_provider: Callable[[], Any]):
        self._db = db_provider

    async def _titles(self, filters: dict[str, dict], limit: int) -> list[tuple[str, dict]]:
        """(content_type, doc) across TMDb collections, most popular first."""
        found = []
        for content_type, flt in filters.items():
            docs = await self._db()[CONTENT_COLLECTIONS[content_type]].find(
                {**flt, **LIVE, "images.backdrop": {"$nin": [None, ""]}}, TITLE_FIELDS
            ).sort("popularity", -1).limit(limit).to_list(None)
            found += [(content_type, d) for d in docs]
        found.sort(key=lambda pair: pair[1].get("popularity") or 0, reverse=True)
        return found[:limit]

    async def editor_picks(self, now: datetime, limit: int) -> list[HeroSlide]:
        pins = await self._db()[TRENDING].find(
            {"pinned": True, "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}]}
        ).sort("computed_at", -1).limit(limit).to_list(None)
        slides = []
        for pin in pins:
            col = CONTENT_COLLECTIONS.get(pin.get("content_type"))
            doc = col and await self._db()[col].find_one({"_id": pin.get("content_id"), **LIVE}, TITLE_FIELDS)
            slide = doc and _title_slide(
                SlideKind.PICK, pin["content_type"], doc,
                subtitle=pin.get("note") or pin.get("reason"),
                fallback_image=pin.get("custom_poster"),
            )
            if slide:
                slides.append(slide)
        return slides

    async def latest_trailers(self, since: datetime, limit: int) -> list[HeroSlide]:
        cutoff = since.strftime("%Y-%m-%dT%H:%M:%S")  # published_at is an ISO string
        flt = {"trailers": {"$elemMatch": {"published_at": {"$gte": cutoff}}}}
        slides = []
        for content_type, doc in await self._titles({k: flt for k in TMDB_KINDS}, limit):
            # The newest trailer in the window, not necessarily the title's main one.
            trailer = max(
                (t for t in doc["trailers"] if (t.get("published_at") or "") >= cutoff),
                key=lambda t: t["published_at"],
            )
            slides.append(_title_slide(
                SlideKind.TRAILER, content_type, doc,
                subtitle=trailer.get("label"),
                video_url=trailer.get("url"),
                date=trailer["published_at"][:10],
            ))
        return [s for s in slides if s]

    async def upcoming_releases(self, start: date, end: date, limit: int) -> list[HeroSlide]:
        span = {"$gte": start.isoformat(), "$lte": end.isoformat()}
        slides = []
        for content_type, doc in await self._titles({k: {RELEASE_FIELD[k]: span} for k in TMDB_KINDS}, limit):
            trailer = (doc.get("trailers") or [{}])[0]
            slides.append(_title_slide(
                SlideKind.RELEASE, content_type, doc,
                date=doc.get(RELEASE_FIELD[content_type]),
                video_url=trailer.get("url"),
            ))
        return [s for s in slides if s]

    async def latest_news(self, since: datetime, limit: int) -> list[HeroSlide]:
        docs = await self._db().news.find(
            {
                "published_at": {"$gte": since.replace(tzinfo=None)},
                "image_url": {"$nin": [None, ""]},
                "duplicate_of": {"$exists": False},  # another source's copy of a story
            },
            {"title": 1, "description": 1, "image_url": 1, "url": 1, "source": 1, "published_at": 1},
        ).sort("published_at", -1).limit(limit).to_list(None)
        return [
            HeroSlide(
                kind=SlideKind.NEWS,
                key=f"news:{d['_id']}",
                title=d["title"],
                image=d["image_url"],
                subtitle=d.get("source"),
                description=(d.get("description") or "")[:280] or None,
                date=d["published_at"].date().isoformat() if isinstance(d.get("published_at"), datetime) else None,
                link_url=d.get("url"),
            )
            for d in docs
            if d.get("title")
        ]
