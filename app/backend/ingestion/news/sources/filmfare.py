import feedparser
import httpx

from app.services.news_date_utils import parse_published_entry, extract_image_url, DEFAULT_NEWS_HEADERS

FILMFARE_RSS = "https://www.filmfare.com/feeds/feeds.xml"


async def fetch_filmfare_news():
    articles = []

    try:
        async with httpx.AsyncClient(timeout=10.0, headers=DEFAULT_NEWS_HEADERS) as client:
            response = await client.get(FILMFARE_RSS, follow_redirects=True)
            feed = feedparser.parse(response.content)

        for entry in feed.entries:
            published_at = parse_published_entry(entry)
            if not published_at:
                continue

            image_url = extract_image_url(entry)

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "source": "filmfare",
                "published_at": published_at,
                "image_url": image_url
            })

    except Exception as e:
        print("Filmfare error:", e)

    print("[Filmfare]:", len(articles))

    return articles
