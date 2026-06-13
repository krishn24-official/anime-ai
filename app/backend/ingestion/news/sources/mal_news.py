import feedparser
import httpx

from app.services.news_date_utils import parse_published_entry

MAL_RSS = "https://myanimelist.net/rss/news.xml"


async def fetch_mal_news():

    articles = []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(MAL_RSS, follow_redirects=True)
            feed = feedparser.parse(response.content)

        for entry in feed.entries:
            published_at = parse_published_entry(entry)
            if not published_at:
                continue

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "source": "myanimelist",
                "published_at": published_at
            })

    except Exception as e:
        print("MAL RSS error:", e)

    print("📊 MAL News:", len(articles))

    return articles