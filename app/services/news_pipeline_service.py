import asyncio
import gc
import time
import re
import httpx
import trafilatura

from app.backend.ingestion.news.sources.animecorner import fetch_animecorner_news
from app.backend.ingestion.news.sources.animenewsnetwork import fetch_ann_news
from app.backend.ingestion.news.sources.crunchyroll import fetch_crunchyroll_news
from app.backend.ingestion.news.sources.mal_news import fetch_mal_news
from app.backend.ingestion.news.sources.boxoffice import fetch_boxoffice_news
from app.backend.ingestion.news.sources.youtube_rss import fetch_youtube_news
from app.backend.ingestion.news.sources.pinkvilla import fetch_pinkvilla_news
from app.backend.ingestion.news.sources.filmfare import fetch_filmfare_news
from app.backend.ingestion.news.sources.bollywood_hungama import fetch_bollywood_hungama_news
from app.backend.ingestion.news.sources.koimoi import fetch_koimoi_news
from app.backend.ingestion.news.sources.variety import fetch_variety_news
from app.backend.ingestion.news.sources.thr import fetch_thr_news
from app.backend.ingestion.news.sources.slashfilm import fetch_slashfilm_news
from app.services.news_category_mapping import get_mapped_category, make_fallback_summary
from app.repositories.news_repository import article_exists, insert_article
from app.services import title_matcher
from app.services import trending_service


LAST_72_HOURS = 72 * 60 * 60
# Alias index is expensive to build (scans all collections). Cache it for 2 h.
_ALIAS_INDEX_CACHE: list = []
_ALIAS_INDEX_BUILT_AT: float = 0.0
_ALIAS_INDEX_TTL: float = 2 * 60 * 60  # 2 hours

SOURCES = [
    fetch_animecorner_news,
    fetch_ann_news,
    fetch_crunchyroll_news,
    fetch_mal_news,
    fetch_boxoffice_news,
    fetch_youtube_news,
    fetch_pinkvilla_news,
    fetch_filmfare_news,
    fetch_bollywood_hungama_news,
    fetch_koimoi_news,
    fetch_variety_news,
    fetch_thr_news,
    fetch_slashfilm_news,
]


async def _get_alias_index() -> list:
    """Return a cached alias index, rebuilding only when the TTL has expired."""
    global _ALIAS_INDEX_CACHE, _ALIAS_INDEX_BUILT_AT
    now = time.monotonic()
    if now - _ALIAS_INDEX_BUILT_AT < _ALIAS_INDEX_TTL and _ALIAS_INDEX_CACHE:
        return _ALIAS_INDEX_CACHE
    try:
        _ALIAS_INDEX_CACHE = await title_matcher.build_alias_index()
        _ALIAS_INDEX_BUILT_AT = now
        print(f"[news_pipeline] alias index rebuilt ({len(_ALIAS_INDEX_CACHE)} entries)")
    except Exception as e:
        print(f"[news_pipeline] failed to build alias index: {e}")
        # Keep the stale cache rather than returning empty
    return _ALIAS_INDEX_CACHE


JUNK_PATTERNS = [
    r"get our breaking news alerts",
    r"comments? on .+ are monitored",
    r"send us a tip using our anon+ymous form",
    r"get our latest stories.*in the feed",
    r"is a part of penske media corporation",
    r"all rights reserved\.?$",
    r"document\.getElementById\(",  # catches any raw script leakage that slips through
]

def is_listicle(title: str) -> bool:
    if not title:
        return False
    # Matches "Top 10", "15 Best", "7 Things", etc.
    return bool(re.search(r'\b(?:top\s)?\d+\s(?:best|worst|things|reasons|times|moments|movies|shows|anime|games|characters)\b|^\d+\s', title, re.IGNORECASE))

def extract_list_items(html_content: str) -> list[str]:
    items = []
    if not html_content:
        return items
    # Extracting text from h2 and h3 tags
    headings = re.findall(r'<h[23][^>]*>(.*?)</h[23]>', html_content, re.IGNORECASE | re.DOTALL)
    for h in headings:
        # strip tags inside heading
        clean_text = re.sub(r'<[^>]+>', '', h).strip()
        if clean_text and len(clean_text) > 3:
            items.append(clean_text)
    return items

from app.services.news_date_utils import DEFAULT_NEWS_HEADERS

async def fetch_full_article_content(url: str) -> tuple[str | None, str | None]:
    """Fetch and extract the main text content of an article from its webpage."""
    if not url:
        return None, None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, headers=DEFAULT_NEWS_HEADERS, follow_redirects=True)
            if r.status_code == 200:
                html = r.text
                result = trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=False,
                    no_fallback=False,
                )
                
                if not result:
                    return None, html
                    
                # Secondary safety net: strip known junk patterns even after extraction
                clean_lines = []
                for line in result.split("\n"):
                    if any(re.search(pattern, line, re.IGNORECASE) for pattern in JUNK_PATTERNS):
                        continue
                    clean_lines.append(line)
                    
                full_text = "\n\n".join(clean_lines)
                return (full_text if full_text.strip() else None), html
    except Exception as e:
        print(f"[news_pipeline] Failed to fetch full article content for {url}: {e}")
    return None, None


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
        return (time.time() - published_at.timestamp()) <= LAST_72_HOURS
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

    alias_index = await _get_alias_index()

    fresh_articles = [a for a in raw_articles if _is_fresh(a)]
    print(f"[news_pipeline] {len(fresh_articles)} fresh (last 72h)")

    saved = 0
    skipped_duplicate = 0
    skipped_unmapped = 0
    processed_urls = set()

    for article in fresh_articles:
        try:
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
                try:
                    full_content, raw_html = await fetch_full_article_content(url)
                    if full_content:
                        # Check for listicle before proceeding
                        if is_listicle(title) and raw_html:
                            list_items = extract_list_items(raw_html)
                            if list_items:
                                from app.services.gemini_service import generate_listicle_article_body
                                listicle_body = await generate_listicle_article_body(title, list_items, full_content)
                                if listicle_body:
                                    full_content = listicle_body

                        article["description"] = full_content
                except Exception as content_err:
                    print(f"[news_pipeline] Error extracting full content for {url}: {content_err}")

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
                    print(f"[news_pipeline] insert error for {url}: {e}")
            else:
                if alias_index:
                    try:
                        await trending_service.scan_article_for_mentions(article, alias_index)
                    except Exception as match_err:
                        print("[news_pipeline] title matcher error:", match_err)
        except Exception as item_err:
            print(f"[news_pipeline] Unexpected item error: {item_err}")

    summary = {
        "fetched": len(raw_articles),
        "fresh": len(fresh_articles),
        "saved": saved,
        "skipped_duplicate": skipped_duplicate,
        "skipped_unmapped": skipped_unmapped,
    }

    # NOTE: recompute_news_trending is intentionally NOT called here.
    # It runs on its own scheduler job (every 30 min) to avoid double execution.

    print("[news_pipeline] done:", summary)

    # Explicitly release memory held by this run's article list.
    gc.collect()

    return summary