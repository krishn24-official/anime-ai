import re
import time
import feedparser
import httpx

from app.services.news_date_utils import parse_published_entry


def clean_description(text: str) -> str:
    """Strip HTML tags and limit to 500 chars."""
    text = re.sub(r"<[^>]+>", "", text or "").strip()
    return text[:500] if text else ""


async def fetch_ann_news():

    url = "https://www.animenewsnetwork.com/all/rss.xml"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True)
        feed = feedparser.parse(response.content)

    articles = []
    last_24_hours = 24 * 60 * 60

    for entry in feed.entries:

        published_at = parse_published_entry(entry)
        if not published_at:
            continue

        if (time.time() - published_at.timestamp()) <= last_24_hours:
            description = ""
            if hasattr(entry, "summary"):
                description = clean_description(entry.summary)

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "source": "animenewsnetwork",
                "description": description,
                "published_at": published_at
            })

    print("📰 ANN:", len(articles))
    return articles