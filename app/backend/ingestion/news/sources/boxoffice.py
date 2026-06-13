import feedparser
import httpx

from app.services.news_date_utils import parse_published_entry

BOXOFFICE_RSS = "https://deadline.com/feed/"


async def fetch_boxoffice_news():
    # Using Deadline RSS as alternative to broken BoxOfficeMojo
    articles = []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(BOXOFFICE_RSS, follow_redirects=True)
            feed = feedparser.parse(response.content)

        for entry in feed.entries:
            published_at = parse_published_entry(entry)
            if not published_at:
                continue

            articles.append({
                "title": entry.title,
                "url": entry.link,
                "source": "boxoffice",
                "published_at": published_at
            })

    except Exception as e:
        print("BoxOffice/Deadline error:", e)

    print("💰 Box Office:", len(articles))

    return articles