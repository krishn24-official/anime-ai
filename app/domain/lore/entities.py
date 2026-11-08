from dataclasses import dataclass, field


@dataclass(frozen=True)
class EpisodeRef:
    """An episode we store, and how to find its wiki page."""

    number: int
    page: str | None  # wiki page name, when known
    title: str | None


@dataclass(frozen=True)
class EpisodePage:
    """What an episode's wiki page says."""

    number: int
    title: str | None
    summary: str  # the richest story section, cleaned
    arc: str | None = None
    chapters: str | None = None  # manga chapters adapted
    filler: bool = False
    characters: tuple[str, ...] = field(default_factory=tuple)  # names linked in the story


@dataclass(frozen=True)
class LorePassage:
    """One searchable passage of a series' lore (what gets embedded)."""

    series_id: str
    section_title: str
    text: str
    episode_number: int | None = None
    character_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RebuildReport:
    series_id: str
    episodes: int  # stored episodes
    pages_found: int  # wiki pages fetched and recognised
    with_story: int  # pages that had a story section
    passages: int
    sample: list[LorePassage]
    applied: bool
    store_stats: dict = field(default_factory=dict)
