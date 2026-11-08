from dataclasses import dataclass

# Content types that can be recommended (singular, as in the rest of the API).
RECOMMENDABLE = ("anime", "manga", "movie", "tv_series")


@dataclass(frozen=True)
class BaseTitle:
    """The title the user liked."""

    content_type: str
    content_id: str
    title: str
    external_id: int | None  # AniList id (anime/manga) or TMDb id (movie/tv_series)


@dataclass(frozen=True)
class Recommendation:
    content_type: str
    external_id: int
    title: str
    votes: int  # how many people recommend it for the base title
    year: int | None = None
    image: str | None = None
    content_id: str | None = None  # set when the title is in our catalog


@dataclass(frozen=True)
class SimilarTitles:
    base: BaseTitle
    items: list[Recommendation]
