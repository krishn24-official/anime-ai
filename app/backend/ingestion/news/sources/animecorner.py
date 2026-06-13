import re
import feedparser
import httpx

from app.services.news_date_utils import parse_published_entry


def clean_description(text: str) -> str:
    """Strip HTML tags and limit to 500 chars."""
    text = re.sub(r"<[^>]+>", "", text or "").strip()
    return text[:500] if text else ""


async def fetch_animecorner_news():

    url = "https://animecorner.me/feed/"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True)
        feed = feedparser.parse(response.content)

    articles = []

    for entry in feed.entries:

        published_at = parse_published_entry(entry)
        if not published_at:
            continue

        description = ""
        if hasattr(entry, "summary"):
            description = clean_description(entry.summary)
        elif hasattr(entry, "content") and entry.content:
            description = clean_description(entry.content[0].get("value", ""))

        articles.append({
            "title": entry.title,
            "url": entry.link,
            "source": "animecorner",
            "description": description,
            "published_at": published_at
        })

    print("📰 AnimeCorner:", len(articles))
    return articles