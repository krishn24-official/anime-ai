import feedparser
import httpx

from app.services.news_date_utils import parse_published_entry

CRUNCHYROLL_RSS = "https://www.crunchyroll.com/rss"


async def fetch_crunchyroll_news():

    articles = []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(CRUNCHYROLL_RSS, follow_redirects=True)
            feed = feedparser.parse(response.content)

        for entry in feed.entries:
            published_at = parse_published_entry(entry)
            if not published_at:
                continue

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "source": "crunchyroll",
                "published_at": published_at
            })

    except Exception as e:
        print("Crunchyroll RSS error:", e)

    print("🍥 Crunchyroll:", len(articles))

    return articles