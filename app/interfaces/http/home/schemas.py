"""HTTP contract for the home page. Field names are the public API; keep them stable."""

from pydantic import BaseModel

from app.domain.home.entities import HeroSlide


class HeroSlideResponse(BaseModel):
    kind: str
    key: str
    title: str
    image: str
    image_is_wide: bool
    subtitle: str | None
    description: str | None
    date: str | None
    content_type: str | None
    content_id: str | None
    video_url: str | None
    link_url: str | None

    @classmethod
    def from_domain(cls, s: HeroSlide) -> "HeroSlideResponse":
        return cls(
            kind=s.kind.value,
            key=s.key,
            title=s.title,
            image=s.image,
            image_is_wide=s.image_is_wide,
            subtitle=s.subtitle,
            description=s.description,
            date=s.date,
            content_type=s.content.content_type if s.content else None,
            content_id=s.content.content_id if s.content else None,
            video_url=s.video_url,
            link_url=s.link_url,
        )
