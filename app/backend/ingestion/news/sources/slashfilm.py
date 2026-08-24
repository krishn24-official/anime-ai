import feedparser
import httpx

from app.services.news_date_utils import parse_published_entry, extract_image_url

SLASHFILM_RSS = "https://www.slashfilm.com/feed/"


async def fetch_slashfilm_news():
    articles = []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(SLASHFILM_RSS, follow_redirects=True)
            feed = feedparser.parse(response.content)

        for entry in feed.entries:
            published_at = parse_published_entry(entry)
            if not published_at:
                continue

            image_url = extract_image_url(entry)

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "source": "slashfilm",
                "published_at": published_at,
                "image_url": image_url
            })

    except Exception as e:
        print("SlashFilm error:", e)

    print("[SlashFilm]:", len(articles))

    return articles
