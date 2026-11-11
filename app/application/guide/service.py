"""Episode & chapter guide: exact facts for lore questions vector search can't answer."""

from app.domain.guide.entities import GuideFacts
from app.domain.guide.ports import ChapterGuide
from app.domain.guide.question import parse_guide_question, term_pattern

MAX_CHAPTERS = 3


class GuideService:
    def __init__(self, guide: ChapterGuide):
        self._guide = guide

    async def facts(self, series_id: str, question: str) -> GuideFacts | None:
        """Chapters/episodes relevant to `question`, or None if there is nothing exact to add."""
        title = await self._guide.series_title(series_id)
        if title is None:
            return None
        q = parse_guide_question(question, ignore=tuple(title.split()))

        if q.chapter is not None:
            chapter = await self._guide.chapter(series_id, q.chapter)
            return GuideFacts(title, f"chapter {q.chapter}", chapters=[chapter]) if chapter else None
        if q.episode is not None:
            episode = await self._guide.episode(series_id, q.episode)
            chapters = await self._guide.chapters_adapted_in(series_id, q.episode)
            if not (episode or chapters):
                return None
            return GuideFacts(
                title, f"episode {q.episode} and the chapters it adapts",
                chapters=chapters, episodes=[episode] if episode else [],
            )
        if not q.terms:
            return None
        patterns = [term_pattern(t) for t in q.terms]
        if q.earliest:
            chapters = await self._guide.earliest_mentioning(series_id, patterns, MAX_CHAPTERS)
            note = f"earliest chapters mentioning {', '.join(q.terms)}"
        else:
            chapters = await self._guide.most_mentioning(series_id, patterns, MAX_CHAPTERS)
            note = f"chapters mentioning {', '.join(q.terms)} most (keyword match)"
        return GuideFacts(title, note, chapters=chapters) if chapters else None
