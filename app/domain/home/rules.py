"""How the home hero is composed. Pure Python, no I/O."""

from app.domain.home.entities import HeroSlide, SlideKind

# Order the kinds take turns in: admin picks lead, then the feed alternates.
KIND_ORDER = (SlideKind.PICK, SlideKind.TRAILER, SlideKind.NEWS, SlideKind.RELEASE)
MAX_PICKS = 2  # picks are hand-chosen, but must not crowd out fresh content


def mix_slides(groups: dict[SlideKind, list[HeroSlide]], limit: int) -> list[HeroSlide]:
    """Interleave the kinds round-robin, each group keeping its own order.

    A title appears once (its first slide wins), so a pinned title with a new
    trailer is not shown twice.
    """
    queues = {kind: list(groups.get(kind, [])) for kind in KIND_ORDER}
    queues[SlideKind.PICK] = queues[SlideKind.PICK][:MAX_PICKS]
    mixed: list[HeroSlide] = []
    seen: set = set()
    while len(mixed) < limit and any(queues.values()):
        for kind in KIND_ORDER:
            while queues[kind]:
                slide = queues[kind].pop(0)
                identity = slide.content or slide.key
                if identity not in seen:
                    seen.add(identity)
                    mixed.append(slide)
                    break
            if len(mixed) == limit:
                break
    return mixed
