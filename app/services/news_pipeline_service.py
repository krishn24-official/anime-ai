import asyncio
import time
import re
import httpx

from app.backend.ingestion.news.sources.animecorner import fetch_animecorner_news
from app.backend.ingestion.news.sources.animenewsnetwork import fetch_ann_news
from app.backend.ingestion.news.sources.crunchyroll import fetch_crunchyroll_news
from app.backend.ingestion.news.sources.mal_news import fetch_mal_news
from app.backend.ingestion.news.sources.boxoffice import fetch_boxoffice_news
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
    fetch_youtube_news,
]


async def fetch_full_article_content(url: str) -> str | None:
    """Fetch and extract the main text content of an article from its webpage."""
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            r = await client.get(url, headers=headers, follow_redirects=True)
            if r.status_code == 200:
                html = r.text
                paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
                text_list = []
                for p in paragraphs:
                    p_clean = re.sub(r"<[^>]+>", "", p).strip()
                    # Decode HTML entities
                    p_clean = (p_clean
                               .replace("&nbsp;", " ")
                               .replace("&amp;", "&")
                               .replace("&lt;", "<")
                               .replace("&gt;", ">")
                               .replace("&#8217;", "'")
                               .replace("&#8216;", "'")
                               .replace("&#8220;", '"')
                               .replace("&#8221;", '"')
                               .replace("&#8212;", "—")
                               .replace("&mdash;", "—")
                               .replace("&ndash;", "–")
                               .replace("&#038;", "&")
                               .replace("&#39;", "'"))
                    
                    # Filter out scripts, ads, menus, and very short lines
                    if "{" in p_clean or "}" in p_clean or "function" in p_clean or "gpt-" in p_clean or "pmcCnx" in p_clean or "blogherads" in p_clean:
                        continue
                        
                    if len(p_clean) > 50 and not any(kw in p_clean.lower() for kw in ["cookie", "subscribe", "newsletter", "follow us", "privacy policy", "terms of service"]):
                        text_list.append(p_clean)
                
                # Combine paragraphs
                full_text = "\n\n".join(text_list[:12])
                return full_text if full_text.strip() else None
    except Exception as e:
        print(f"[news_pipeline] Failed to fetch full article content for {url}: {e}")
    return None


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
    processed_urls = set()

    for article in fresh_articles:

        url = article.get("url")
        title = article.get("title")

        if not url or not title:
            continue

        if url in processed_urls or await article_exists(url):
            skipped_duplicate += 1
            continue

        processed_urls.add(url)

        mapped_category = get_mapped_category(article)

        if not mapped_category:
            skipped_unmapped += 1
            continue

        # If it's a website article, fetch full content
        if article.get("source") != "youtube":
            full_content = await fetch_full_article_content(url)
            if full_content:
                article["description"] = full_content

        article["category"] = mapped_category
        article["summary"] = make_fallback_summary(article)

        try:
            await insert_article(article)
            saved += 1

            try:
                from app.services.websocket_manager import manager
                from app.services.news_service import _serialize
                await manager.broadcast({
                    "type": "NEW_ARTICLE",
                    "data": _serialize(article)
                })
            except Exception as ws_err:
                print("[news_pipeline] websocket broadcast error:", ws_err)
        except Exception as e:
            if "duplicate key" in str(e).lower() or "11000" in str(e):
                skipped_duplicate += 1
            else:
                raise e

    summary = {
        "fetched": len(raw_articles),
        "fresh": len(fresh_articles),
        "saved": saved,
        "skipped_duplicate": skipped_duplicate,
        "skipped_unmapped": skipped_unmapped,
    }

    print("[news_pipeline] done:", summary)
    return summary