from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChapterInfo:
    number: int
    title: str | None
    summary: str | None  # short summary (falls back to the start of the long one)
    arc: str | None = None
    japanese_title: str | None = None
    anime_episodes: tuple[int, ...] = field(default_factory=tuple)  # episodes adapting it


@dataclass(frozen=True)
class EpisodeInfo:
    number: int
    title: str | None
    summary: str | None
    arc: str | None = None
    filler: bool = False
    chapters_covered: str | None = None  # e.g. "1" or "2-3"


@dataclass(frozen=True)
class GuideFacts:
    """What the episode/chapter guide knows that is relevant to a question."""

    series_title: str
    note: str  # how the entries were chosen, e.g. "earliest chapters mentioning luffy, gear 5"
    chapters: list[ChapterInfo] = field(default_factory=list)
    episodes: list[EpisodeInfo] = field(default_factory=list)
