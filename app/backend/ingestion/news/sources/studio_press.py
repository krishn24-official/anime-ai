import time
import feedparser
import httpx

from app.services.news_date_utils import normalize_datetime, parse_published_entry

# General entertainment press feeds (Collider covers movies/TV)
PRESS_FEEDS = [
    "https://collider.com/feed/",
]


async def fetch_studio_press():

    articles = []

    async with httpx.AsyncClient() as client:
        for feed_url in PRESS_FEEDS:
            response = await client.get(feed_url, follow_redirects=True)
            rss = feedparser.parse(response.content)

        for entry in rss.entries[:5]:
            published_at = parse_published_entry(entry)
            if not published_at:
                published_at = normalize_datetime(time.time())

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "source": "entertainment_news",
                "published_at": published_at
            })

    print("🏢 Studio press:", len(articles))

    return articles