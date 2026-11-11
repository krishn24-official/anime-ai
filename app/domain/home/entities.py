from dataclasses import dataclass
from enum import Enum

from app.domain.shared.content import ContentRef


class SlideKind(str, Enum):
    PICK = "pick"  # pinned by an admin on the trending list
    TRAILER = "trailer"  # a newly published trailer
    RELEASE = "release"  # a title releasing soon
    NEWS = "news"  # a recent news article


@dataclass(frozen=True)
class HeroSlide:
    """One card of the home page hero."""

    kind: SlideKind
    key: str  # unique per slide
    title: str
    image: str
    image_is_wide: bool = True  # False: a portrait poster, shown framed instead of stretched
    subtitle: str | None = None  # trailer name, news source, ...
    description: str | None = None
    date: str | None = None  # ISO date: release date or publish date
    content: ContentRef | None = None  # opens the title's detail page
    video_url: str | None = None  # plays in the trailer player
    link_url: str | None = None  # external article
