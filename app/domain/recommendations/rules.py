"""Which recommendations to show. Pure Python."""

from app.domain.recommendations.entities import BaseTitle, Recommendation


def _same_franchise(title: str, picked: list[str]) -> bool:
    """"Naruto: Shippuden" after "Naruto", "Vinland Saga Season 2" after "Vinland Saga"."""
    t = title.lower()
    return any(t.startswith(p.lower()) for p in picked)


def pick(recs: list[Recommendation], base: BaseTitle, limit: int) -> list[Recommendation]:
    """Most recommended first; never the base title or its franchise; one title per franchise."""
    seen = {(base.content_type, base.external_id)}
    titles = [base.title]
    picked = []
    for rec in sorted(recs, key=lambda r: r.votes, reverse=True):
        key = (rec.content_type, rec.external_id)
        if key in seen or rec.votes <= 0 or not rec.title or _same_franchise(rec.title, titles):
            continue
        seen.add(key)
        titles.append(rec.title)
        picked.append(rec)
        if len(picked) == limit:
            break
    return picked
