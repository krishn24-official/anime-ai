"""Rules for a title's videos (movies and TV series). Pure Python, no I/O.

A title stores two lists:
  trailers: Trailer/Teaser videos, best first. trailers[0] is what "Play trailer" plays.
  extras:   other videos (featurettes, clips, behind the scenes, ...), shown separately.

"Best" = in a preferred language (English, then the title's original language),
official, a Trailer before a Teaser, a real trailer before spots/promos (TMDb types
"TV Spot #9" or "Special Look" as Trailer too), newest first.
"""

import re

TRAILER_TYPES = ("Trailer", "Teaser")
MAX_TRAILERS = 5
MAX_EXTRAS = 8

# Labels TMDb uses as video types. Stored items whose label is not one of these
# (and that carry no "type") were typed in by an admin.
TMDB_VIDEO_TYPES = frozenset(
    {"Trailer", "Teaser", "Clip", "Featurette", "Behind the Scenes", "Bloopers", "Opening Credits", "Recap"}
)

# Whole-word matches (lookarounds instead of \b, which is easy to mangle when escaped).
_WORD_START, _WORD_END = r"(?<!\w)", r"(?!\w)"
# Named like a promo rather than the trailer itself.
_PROMO_NAME = re.compile(
    _WORD_START
    + r"(tv spot|spot|promo|special look|sneak peek|first look|tour|reaction|review|recap)"
    + _WORD_END,
    re.IGNORECASE,
)
_OFFICIAL_TRAILER = re.compile(_WORD_START + r"official" + _WORD_END + r".*" + _WORD_START + r"trailer", re.IGNORECASE)
_TRAILER = re.compile(_WORD_START + r"trailer", re.IGNORECASE)


def youtube_url(key: str) -> str:
    return f"https://www.youtube.com/watch?v={key}"


def _name_rank(name: str) -> int:
    name = name or ""
    if _PROMO_NAME.search(name):
        return 3
    if _OFFICIAL_TRAILER.search(name):
        return 0
    if _TRAILER.search(name):
        return 1
    return 2


def _type_rank(video_type: str) -> int:
    return TRAILER_TYPES.index(video_type) if video_type in TRAILER_TYPES else len(TRAILER_TYPES)


def _inverted(text: str) -> str:
    """A key that sorts ISO timestamps newest-first."""
    return "".join(chr(0x10FFFF - ord(c)) for c in text)


def organize_tmdb_videos(
    results: list[dict], preferred_languages: tuple[str, ...] = ("en",)
) -> tuple[list[dict], list[dict]]:
    """Split TMDb video results into (trailers, extras), best first, capped.

    Only YouTube videos are kept (the site plays YouTube embeds).
    """
    seen: set[str] = set()
    videos = []
    for v in results or []:
        if v.get("site") != "YouTube" or not v.get("key") or v["key"] in seen:
            continue
        seen.add(v["key"])
        videos.append(
            {
                "url": youtube_url(v["key"]),
                "label": v.get("name") or v.get("type") or "Video",
                "type": v.get("type") or "Video",
                "official": bool(v.get("official")),
                "published_at": v.get("published_at"),
                "language": v.get("iso_639_1"),
            }
        )

    def sort_key(video: dict) -> tuple:
        lang = video.get("language")
        lang_rank = preferred_languages.index(lang) if lang in preferred_languages else len(preferred_languages)
        return (
            lang_rank,
            not video["official"],
            _type_rank(video["type"]),
            _name_rank(video["label"]),
            _inverted(video.get("published_at") or ""),
        )

    videos.sort(key=sort_key)
    trailers = [v for v in videos if v["type"] in TRAILER_TYPES][:MAX_TRAILERS]
    extras = [v for v in videos if v["type"] not in TRAILER_TYPES][:MAX_EXTRAS]
    return trailers, extras


def split_stored_videos(videos: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split a legacy stored list (every video mixed together) into (trailers, extras).

    Items typed in by an admin (unknown label, no type) count as trailers. Trailer
    videos keep their stored order but Trailers come before Teasers.
    """
    trailers, extras = [], []
    for v in videos or []:
        if not isinstance(v, dict) or not v.get("url"):
            continue
        video_type = v.get("type") or v.get("label")
        if video_type in TMDB_VIDEO_TYPES and video_type not in TRAILER_TYPES:
            extras.append(v)
        else:
            trailers.append(v)
    trailers.sort(key=lambda v: _type_rank(v.get("type") or v.get("label") or ""))
    return trailers[:MAX_TRAILERS], extras[:MAX_EXTRAS]


def has_manual_trailers(videos: list[dict]) -> bool:
    """True if any stored trailer was typed in by an admin (never overwrite those)."""
    return any(
        isinstance(v, dict) and "type" not in v and v.get("label") not in TMDB_VIDEO_TYPES
        for v in videos or []
    )


def trailer_urls_changed(old: list[dict] | None, new: list[dict] | None) -> bool:
    urls = lambda vs: [v.get("url") for v in vs or [] if isinstance(v, dict)]  # noqa: E731
    return urls(old) != urls(new)
