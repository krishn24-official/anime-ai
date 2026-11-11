"""Glue between stored news and the duplicate-story rule (app/domain/news/duplicates.py)."""

from app import container
from app.domain.news.duplicates import Headline, parse_headline


async def headlines(articles: list[dict]) -> list[Headline]:
    """Parsed headlines of article dicts (title, published_at), with embeddings when
    available (else word matching only)."""
    titles = [a.get("title") or "" for a in articles]
    embedder = container.headline_embedder()
    vectors = (await embedder.embed(titles) if embedder else None) or [None] * len(titles)
    return [parse_headline(t, v, a.get("published_at")) for t, v, a in zip(titles, vectors, articles)]


async def with_headlines(docs: list[dict]) -> list[tuple[object, str | None, Headline]]:
    """Stored articles -> (id, source, headline) rows, as find_original expects."""
    return [(d["_id"], d.get("source"), h) for d, h in zip(docs, await headlines(docs))]
