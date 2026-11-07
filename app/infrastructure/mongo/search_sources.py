"""How each searchable MongoDB collection maps onto a SearchDocument.

Shared by the regex index and the Atlas search catalog so both return
identical documents. The `display` dicts are the public /search response shape.
"""

from dataclasses import dataclass
from typing import Callable

from app.domain.search.entities import SearchDocument


def _get(doc: dict, path: str):
    value = doc
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _strings(*values) -> list[str]:
    out: list[str] = []
    for v in values:
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
        elif isinstance(v, (list, tuple)):
            out.extend(s.strip() for s in v if isinstance(s, str) and s.strip())
    return out


def _number(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return 0.0
    return 0.0


@dataclass(frozen=True)
class SearchSource:
    kind: str
    collection: str
    name_fields: tuple[str, ...]  # matched by the regex index (title + aliases)
    projection: dict
    title: Callable[[dict], str | None]
    aliases: Callable[[dict], list[str]]
    display: Callable[[dict], dict]
    rating: Callable[[dict], float] = lambda d: 0.0
    popularity: Callable[[dict], float] = lambda d: 0.0
    image: Callable[[dict], str | None] = lambda d: None
    # Some collections store is_deleted=False, others may omit it.
    not_deleted: dict = None  # type: ignore[assignment]

    def to_document(self, doc: dict) -> SearchDocument | None:
        title = self.title(doc)
        if not title:
            return None
        aliases = [a for a in dict.fromkeys(self.aliases(doc)) if a != title]
        return SearchDocument(
            kind=self.kind,
            id=str(doc["_id"]),
            title=title,
            aliases=tuple(aliases),
            rating=self.rating(doc),
            popularity=self.popularity(doc),
            image=self.image(doc) or None,
            display=self.display(doc),
        )


def _anime_title(d):
    return _get(d, "title.english") or _get(d, "title.romaji") or _get(d, "title.japanese")


SOURCES: dict[str, SearchSource] = {
    "anime": SearchSource(
        kind="anime",
        collection="anime",
        name_fields=("title.english", "title.romaji", "title.japanese", "synonyms"),
        projection={"title": 1, "synonyms": 1, "images": 1, "year": 1, "rating": 1},
        title=_anime_title,
        aliases=lambda d: _strings(
            _get(d, "title.romaji"), _get(d, "title.japanese"), d.get("synonyms")
        ),
        display=lambda d: {
            "_id": str(d["_id"]),
            "title": d.get("title"),
            "images": d.get("images"),
            "year": d.get("year"),
        },
        rating=lambda d: _number(_get(d, "rating.anilist")) / 10,
        image=lambda d: _get(d, "images.poster"),
        not_deleted={"is_deleted": False},
    ),
    "manga": SearchSource(
        kind="manga",
        collection="manga",
        name_fields=("name", "native_name"),
        projection={"name": 1, "native_name": 1, "cover_image": 1, "status": 1},
        title=lambda d: d.get("name"),
        aliases=lambda d: _strings(d.get("native_name")),
        display=lambda d: {
            "_id": str(d["_id"]),
            "name": d.get("name"),
            "cover_image": d.get("cover_image"),
            "status": d.get("status"),
        },
        image=lambda d: d.get("cover_image"),
        not_deleted={"is_deleted": {"$ne": True}},
    ),
    "movies": SearchSource(
        kind="movies",
        collection="movies",
        name_fields=("title", "original_title"),
        projection={"title": 1, "original_title": 1, "year": 1, "images": 1, "genres": 1, "rating": 1},
        title=lambda d: d.get("title"),
        aliases=lambda d: _strings(d.get("original_title")),
        display=lambda d: {
            "_id": str(d["_id"]),
            "title": d.get("title"),
            "year": d.get("year"),
            "images": d.get("images"),
            "genres": d.get("genres"),
        },
        rating=lambda d: _number(_get(d, "rating.tmdb")),
        popularity=lambda d: _number(_get(d, "rating.tmdb_vote_count")),
        image=lambda d: _get(d, "images.poster"),
        not_deleted={"is_deleted": {"$ne": True}},
    ),
    "tv_series": SearchSource(
        kind="tv_series",
        collection="tv_series",
        name_fields=("title", "original_title"),
        projection={
            "title": 1, "original_title": 1, "year": 1, "images": 1,
            "genres": 1, "total_seasons": 1, "rating": 1,
        },
        title=lambda d: d.get("title"),
        aliases=lambda d: _strings(d.get("original_title")),
        display=lambda d: {
            "_id": str(d["_id"]),
            "title": d.get("title"),
            "year": d.get("year"),
            "images": d.get("images"),
            "genres": d.get("genres"),
            "total_seasons": d.get("total_seasons"),
        },
        rating=lambda d: _number(_get(d, "rating.imdb")),
        popularity=lambda d: _number(_get(d, "rating.imdb_votes")),
        image=lambda d: _get(d, "images.poster"),
        not_deleted={"is_deleted": {"$ne": True}},
    ),
    "characters": SearchSource(
        kind="characters",
        collection="characters",
        name_fields=("name", "native_name"),
        projection={"name": 1, "native_name": 1, "images.profile": 1, "role": 1},
        title=lambda d: d.get("name"),
        aliases=lambda d: _strings(d.get("native_name")),
        display=lambda d: {
            "_id": str(d["_id"]),
            "name": d.get("name"),
            "images": {"profile": _get(d, "images.profile")},
            "role": d.get("role"),
        },
        # Main characters are what people usually look for.
        popularity=lambda d: 1.0 if d.get("role") == "main" else 0.0,
        image=lambda d: _get(d, "images.profile"),
        not_deleted={"is_deleted": False},
    ),
    "actors": SearchSource(
        kind="actors",
        collection="actors",
        name_fields=("name",),
        projection={"name": 1, "images.profile": 1},
        title=lambda d: d.get("name"),
        aliases=lambda d: [],
        display=lambda d: {
            "_id": str(d["_id"]),
            "name": d.get("name"),
            "images": {"profile": _get(d, "images.profile")},
        },
        image=lambda d: _get(d, "images.profile"),
        not_deleted={"is_deleted": False},
    ),
    "organizations": SearchSource(
        kind="organizations",
        collection="organizations",
        name_fields=("name",),
        projection={"name": 1, "type": 1, "images": 1, "anime_ids": 1, "manga_id": 1},
        title=lambda d: d.get("name"),
        aliases=lambda d: [],
        display=lambda d: {
            "id": str(d["_id"]),
            "name": d.get("name"),
            "type": d.get("type"),
            "images": d.get("images", {"logo": "", "banner": ""}),
            "anime_ids": d.get("anime_ids", []),
            "manga_id": d.get("manga_id"),
        },
        image=lambda d: _get(d, "images.logo"),
        not_deleted={"is_deleted": {"$ne": True}},
    ),
}
