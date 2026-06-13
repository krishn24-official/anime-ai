import asyncio
import time

from app.backend.ingestion.news.sources.animecorner import fetch_animecorner_news
from app.backend.ingestion.news.sources.animenewsnetwork import fetch_ann_news
from app.backend.ingestion.news.sources.crunchyroll import fetch_crunchyroll_news
from app.backend.ingestion.news.sources.mal_news import fetch_mal_news
from app.backend.ingestion.news.sources.boxoffice import fetch_boxoffice_news
from app.backend.ingestion.news.sources.screenrant import fetch_screenrant_news
from app.backend.ingestion.news.sources.studio_press import fetch_studio_press
from app.backend.ingestion.news.sources.youtube_rss import fetch_youtube_news

from app.services.news_category_mapping import get_mapped_category, make_fallback_summary
from app.repositories.news_repository import article_exists, insert_article


LAST_24_HOURS = 24 * 60 * 60

SOURCES = [
    fetch_animecorner_news,
    fetch_ann_news,
    fetch_crunchyroll_news,
    fetch_mal_news,
    fetch_boxoffice_news,
    fetch_screenrant_news,
    fetch_studio_press,
    fetch_youtube_news,
]


async def _fetch_all_sources():
    results = await asyncio.gather(*(source() for source in SOURCES), return_exceptions=True)

    articles = []
    for result in results:
        if isinstance(result, Exception):
            print("[news_pipeline] source error:", result)
            continue
        articles.extend(result or [])

    return articles


def _is_fresh(article: dict) -> bool:
    published_at = article.get("published_at")
    if not published_at:
        return False

    try:
        return (time.time() - published_at.timestamp()) <= LAST_24_HOURS
    except Exception:
        return False


async def run_news_pipeline():
    """
    Fetch from all sources, filter for freshness, dedupe against existing
    DB entries, categorize via source/channel mapping (no AI calls), and
    save to the 'news' collection.

    Articles whose source/channel isn't in the mapping are skipped
    (skipped_unmapped) rather than discarded silently -- add them to
    news_category_mapping.py to start saving them.

    Returns a summary dict.
    """

    raw_articles = await _fetch_all_sources()
    print(f"[news_pipeline] fetched {len(raw_articles)} raw articles")

    fresh_articles = [a for a in raw_articles if _is_fresh(a)]
    print(f"[news_pipeline] {len(fresh_articles)} fresh (last 24h)")

    saved = 0
    skipped_duplicate = 0
    skipped_unmapped = 0

    for article in fresh_articles:

        url = article.get("url")
        title = article.get("title")

        if not url or not title:
            continue

        if await article_exists(url):
            skipped_duplicate += 1
            continue

        mapped_category = get_mapped_category(article)

        if not mapped_category:
            skipped_unmapped += 1
            continue

        article["category"] = mapped_category
        article["summary"] = make_fallback_summary(article)

        await insert_article(article)
        saved += 1

    summary = {
        "fetched": len(raw_articles),
        "fresh": len(fresh_articles),
        "saved": saved,
        "skipped_duplicate": skipped_duplicate,
        "skipped_unmapped": skipped_unmapped,
    }

    print("[news_pipeline] done:", summary)
    return summary