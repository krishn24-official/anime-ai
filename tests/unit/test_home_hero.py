from datetime import datetime, timedelta, timezone

from app.application.home.service import HomeService
from app.domain.home.entities import HeroSlide, SlideKind
from app.domain.home.rules import MAX_PICKS, mix_slides
from app.domain.shared.content import ContentRef

PICK, TRAILER, NEWS, RELEASE = SlideKind.PICK, SlideKind.TRAILER, SlideKind.NEWS, SlideKind.RELEASE


def slide(kind, key, content_id=None):
    content = ContentRef("movie", content_id) if content_id else None
    return HeroSlide(kind=kind, key=key, title=key, image="img", content=content)


def test_kinds_take_turns_and_picks_are_capped():
    groups = {
        PICK: [slide(PICK, f"p{i}", f"m_p{i}") for i in range(4)],
        TRAILER: [slide(TRAILER, "t1", "m_t1"), slide(TRAILER, "t2", "m_t2")],
        NEWS: [slide(NEWS, "n1")],
    }
    keys = [s.key for s in mix_slides(groups, limit=10)]
    assert keys == ["p0", "t1", "n1", "p1", "t2"]
    assert sum(k.startswith("p") for k in keys) == MAX_PICKS


def test_a_title_is_shown_once_and_limit_is_respected():
    groups = {
        PICK: [slide(PICK, "pick", "m_same")],
        TRAILER: [slide(TRAILER, "trailer", "m_same"), slide(TRAILER, "other", "m_other")],
        RELEASE: [slide(RELEASE, "r1", "m_r1")],
    }
    assert [s.key for s in mix_slides(groups, limit=10)] == ["pick", "other", "r1"]
    assert len(mix_slides(groups, limit=2)) == 2


class FakeSource:
    def __init__(self, fail_news=False):
        self.calls = 0
        self.fail_news = fail_news

    async def editor_picks(self, now, limit):
        self.calls += 1
        return [slide(PICK, "p", "m_p")]

    async def latest_trailers(self, since, limit):
        self.trailers_since = since
        return [slide(TRAILER, "t", "m_t")]

    async def upcoming_releases(self, start, end, limit):
        return [slide(RELEASE, "r", "m_r")]

    async def latest_news(self, since, limit):
        if self.fail_news:
            raise RuntimeError("news down")
        return [slide(NEWS, "n")]


async def test_feed_survives_a_failing_source_and_is_cached():
    now = datetime(2026, 11, 8, tzinfo=timezone.utc)
    clock = {"now": now}
    source = FakeSource(fail_news=True)
    service = HomeService(source, clock=lambda: clock["now"], cache_ttl=timedelta(minutes=10))

    assert [s.key for s in await service.hero_feed()] == ["p", "t", "r"]
    assert source.trailers_since == now - timedelta(hours=48)  # only fresh trailers
    await service.hero_feed()
    assert source.calls == 1  # served from cache
    clock["now"] = now + timedelta(minutes=11)
    await service.hero_feed()
    assert source.calls == 2
