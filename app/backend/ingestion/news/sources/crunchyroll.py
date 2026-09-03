import feedparser
import httpx

from app.services.news_date_utils import parse_published_entry, extract_image_url

CRUNCHYROLL_RSS = "https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss"


async def fetch_crunchyroll_news():

    articles = []

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            response = await client.get(CRUNCHYROLL_RSS, follow_redirects=True)
            feed = feedparser.parse(response.content)

        for entry in feed.entries:
            published_at = parse_published_entry(entry)
            if not published_at:
                continue

            image_url = extract_image_url(entry)
            description = ""
            if hasattr(entry, "summary"):
                description = entry.summary
            elif hasattr(entry, "description"):
                description = entry.description

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "source": "crunchyroll",
                "description": description[:500] if description else "",
                "published_at": published_at,
                "image_url": image_url
            })

    except Exception as e:
        print("Crunchyroll RSS error:", e)

    print("[Crunchyroll]:", len(articles))

    return articles