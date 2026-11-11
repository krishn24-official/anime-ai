import re

from app.application.guide.service import GuideService
from app.domain.guide.entities import ChapterInfo, EpisodeInfo
from app.domain.guide.question import is_exact_question, parse_guide_question, term_pattern


def test_parses_numbers_ordinals_and_terms():
    q = parse_guide_question("what's the name of one piece first chapter?", ignore=("One", "Piece"))
    assert q.chapter == 1 and q.terms == ()
    assert parse_guide_question("summary of chapter 1044").chapter == 1044
    assert parse_guide_question("what happens in ep. 1071").episode == 1071
    q = parse_guide_question("in which episode luffy first time used gear 5?")
    assert q.episode is None and q.earliest and q.terms == ("luffy", "gear 5")


def test_number_terms_match_spelled_out_forms():
    pattern = term_pattern("gear 5")
    assert re.search(pattern, "Luffy awakens Gear 5", re.I)
    assert re.search(pattern, "the power of Gear Fifth", re.I)
    assert not re.search(pattern, "Gear 4 Boundman", re.I)


class FakeGuide:
    CH1044 = ChapterInfo(1044, "Warrior of Liberation", "Luffy awakens Gear 5.", anime_episodes=(1071,))

    async def series_title(self, series_id):
        return "One Piece" if series_id == "anime_one_piece" else None

    async def chapter(self, series_id, number):
        return ChapterInfo(1, "Romance Dawn", "Luffy sets out.") if number == 1 else None

    async def episode(self, series_id, number):
        return EpisodeInfo(1071, "Luffy's Peak", "Gear 5 awakens.") if number == 1071 else None

    async def chapters_adapted_in(self, series_id, episode):
        return [self.CH1044] if episode == 1071 else []

    async def earliest_mentioning(self, series_id, patterns, limit):
        self.patterns = patterns
        return [self.CH1044]

    async def most_mentioning(self, series_id, patterns, limit):
        return [ChapterInfo(540, "Impel Down", "...Luffy enters Impel Down...")] if len(patterns) >= 2 else []


async def test_service_picks_the_right_lookup():
    guide = FakeGuide()
    service = GuideService(guide)
    facts = await service.facts("anime_one_piece", "what's the name of one piece first chapter?")
    assert facts.chapters[0].title == "Romance Dawn"
    facts = await service.facts("anime_one_piece", "in which episode luffy first time used gear 5?")
    assert facts.chapters[0].anime_episodes == (1071,) and len(guide.patterns) == 2
    facts = await service.facts("anime_one_piece", "what happens in episode 1071?")
    assert facts.episodes[0].title == "Luffy's Peak" and facts.chapters[0].number == 1044
    assert await service.facts("anime_naruto", "first chapter?") is None  # no guide for that series
    facts = await service.facts("anime_one_piece", "what happened to luffy in impel down?")
    assert facts.chapters[0].number == 540 and "keyword" in facts.note  # keyword retrieval
    assert await service.facts("anime_one_piece", "what is this?") is None  # no terms at all


def test_exact_questions_skip_the_models_tool_choice():
    assert is_exact_question("naruto's first chapter name")
    assert is_exact_question("one piece first chapter name")
    assert is_exact_question("what happens in bleach episode 5?")
    assert is_exact_question("when did luffy first use gear 5")
    assert not is_exact_question("who is the first hokage?")  # a bare "first" is not "first time"
    assert not is_exact_question("why is luffy so strong?")
