"""HTTP contract for trending. Field names are the public API; keep them stable."""

from datetime import datetime

from pydantic import BaseModel

from app.domain.trending.entities import TrendingItem


class TrendingItemResponse(BaseModel):
    content_type: str
    content_id: str
    title: str
    poster_image: str | None
    reason: str | None
    pinned: bool
    set_at: datetime | None
    note: str | None

    @classmethod
    def from_domain(cls, item: TrendingItem) -> "TrendingItemResponse":
        return cls(
            content_type=item.content_type,
            content_id=item.content_id,
            title=item.title,
            poster_image=item.poster_image,
            reason=item.reason,
            pinned=item.pinned,
            set_at=item.set_at,
            note=item.note,
        )


class StatusResponse(BaseModel):
    status: str = "ok"


class SearchClickRequest(BaseModel):
    content_type: str
    content_id: str
    query: str
