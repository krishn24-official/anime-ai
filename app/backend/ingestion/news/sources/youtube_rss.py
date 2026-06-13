import re
import time
import feedparser
import httpx

from app.services.news_date_utils import parse_published_entry

CHANNELS = {
    "IGN": "UCKy1dAqELo0zrOtPkf0eTMw",
    "GameSpot": "UC5CE6nbu1tjSGha-a_cHAFA",
    "PlayStation": "UCBsbrudhKRrT9zs8iNOEjjw",
    "Xbox": "UCydtMNspoPAlqBjFSGnigSw",
    "Nintendo": "UCgK_2VQWwigtTr_5TviGy2w",

    "Shonen Jump": "UC47AYUs8AVU1QsT5LhpXjaw",
    "Aniplex USA": "UCDb0peSmF5rLX7BvuTcJfCw",
    "Toei Animation": "UCLhgIX2L5ZCaWdlaxR_oTAg",
    "Crunchyroll": "UC6pGDc4bFGD1_36IKv3FnYg",

    "Netflix": "UCGie8GMlUo3kBKIopdvumVQ",
    "Marvel": "UCxwitsUVNzwS5XBSC5UQV8Q",
    "DC": "UCiifkYAs_bq1pt_zbNAzYGg",
}


def sanitize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"[\U00010000-\U0010FFFF]", "", text)
    text = re.sub(r"[\uFE00-\uFE0F]", "", text)
    return text.strip()


def extract_description(entry) -> str:
    description = ""

    if hasattr(entry, "summary"):
        description = entry.summary
    elif hasattr(entry, "description"):
        description = entry.description
    elif hasattr(entry, "content") and entry.content:
        description = entry.content[0].get("value", "")

    description = re.sub(r"<[^>]+>", "", description).strip()
    description = sanitize_text(description)

    return description[:500] if description else ""


async def fetch_youtube_news():

    articles = []
    last_24_hours = 24 * 60 * 60

    async with httpx.AsyncClient() as client:
        for name, channel_id in CHANNELS.items():

            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

            try:
                response = await client.get(url, follow_redirects=True)
                feed = feedparser.parse(response.content)

                for entry in feed.entries:
                    published_at = parse_published_entry(entry)
                    if not published_at:
                        continue

                    if (time.time() - published_at.timestamp()) <= last_24_hours:
                        video_id = getattr(entry, "yt_videoid", None)
                        description = extract_description(entry)

                        articles.append({
                            "title": sanitize_text(entry.title),
                            "url": f"https://youtube.com/watch?v={video_id}" if video_id else getattr(entry, "link", ""),
                            "source": "youtube",
                            "youtube_channel": name,
                            "description": description,
                            "published_at": published_at
                        })

            except Exception as e:
                print("YouTube RSS error:", name, e)

    print("📺 YouTube:", len(articles))
    return articles