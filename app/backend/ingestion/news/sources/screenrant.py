import time
import feedparser
import httpx

from app.services.news_date_utils import normalize_datetime, parse_published_entry

SCREENRANT_RSS = "https://www.screenrant.com/feed/"


async def fetch_screenrant_news():
    articles = []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(SCREENRANT_RSS, follow_redirects=True)
            feed = feedparser.parse(response.content)

        for entry in feed.entries[:15]:
            published_at = parse_published_entry(entry)
            if not published_at:
                published_at = normalize_datetime(time.time())

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "source": "screenrant",
                "published_at": published_at
            })

    except Exception as e:
        print("ScreenRant error:", e)

    print("🎬 ScreenRant news:", len(articles))

    return articles