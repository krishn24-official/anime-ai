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
    "Eurogamer": "UCciKycgzURdymx-GRSY2_dA",
    "PC Gamer": "UCgaPRP68bbyHnfkPhWWBrNw",

    # 🎮 Game Publishers
    "Bandai Namco": "UCUfPqBj40lJtfAf78WtEGlQ",
    "Ubisoft": "UCBMvc6jvuTxH6TNo9ThpYjg",
    "Square Enix": "UCH3sMKVJ2P7hm7ROBy5FHJg",
    "Capcom": "UCbReH8gzVeGr6wuQHEOiHFA",
    "Epic Games": "UC5Qk8mWBwtMyEj7iQQYRk1A",
    "SEGA": "UCWfXR0-F7MI-TbqikgEdJc",

    # 📚 Manga / Anime Publishers
    "Shonen Jump": "UC47AYUs8AVU1QsT5LhpXjaw",
    "Kodansha": "UCo-Z2r9KeM1uv11uLdnsBMg",
    "VIZ Media": "UCcckdFKX9yMZBiTDb7HNmhw",
    "Aniplex USA": "UCDb0peSmF5rLX7BvuTcJfCw",
    "Toei Animation": "UCLhgIX2L5ZCaWdlaxR_oTAg",
    "Mappa": "UCjfAEJZdfbIjVHdo5yODfyQ",

    # 🎥 Anime Streaming
    "Crunchyroll": "UC6pGDc4bFGD1_36IKv3FnYg",
    "Netflix Anime": "UCWOA1ZGywLbqmigxE4Qlvuw",
    "Ani-One Asia": "UC0wNSTMWIL3qaorLx0jie6A",

    # 📺 Streaming Platforms
    "Netflix": "UCGie8GMlUo3kBKIopdvumVQ",
    "Prime Video": "UCyouSlyNTfwX_pnGvlfIL3Q",
    "Disney+": "UC_5niPa-d35gg88HaS7RrIw",
    "Apple TV+": "UC1Myj674wRVXB9I4c6Hm5zA",
    "HBO": "UCVTQuK2CaWaTgSsoNkn5AiQ",

    # 🎬 Movie Studios
    "Marvel": "UCxwitsUVNzwS5XBSC5UQV8Q",
    "DC": "UCiifkYAs_bq1pt_zbNAzYGg",
    "Warner Bros": "UCjmJDM5pRKbUlVIzDYYWb6g",
    "Sony Pictures": "UCP8AC-LXl5Jmp64IRIsdacg",
    "Universal Pictures": "UCq7OHvWO6Z3u-LztFdrcU-g",
    "Paramount Pictures": "UCF9imwPMSGz4Vq1NiTWCC7g",
    "Lionsgate": "UCFR6sruqEq52xEqjE84tq4A",
    "20th Century Studios": "UCi_MYg8bBEbfIHfLRxGd_Eg",
    "A24": "UCuPivVjnfNo4mb3Oog_frZg",

    # 🎬 Trailer Channels
    "Rotten Tomatoes Trailers": "UCE0Wkd9Jcn2-TNo5G8bLQrA",

    # # 🇮🇳 Indian Studios
    # "T-Series": "UChz5aEi3dfrDVC8-YJsMUDA",
    # "Yash Raj Films": "UCbTLwN10NoCU4WDzLf1JMOA",
    # "Hombale Films": "UCarJoVXH0T2pdtcHBu9J8Bw",

    # # 🇮🇳 OTT India
    # "Netflix India": "UCim0ZIz8SAQGPvg4mJHG3JA",
    # "Prime Video India": "UC4zWG9LccdWGUlF77LZ8toA",
    # "Jio Studios": "UCcXQd6kHKm0b41x8zMVMmMg"
}

YOUTUBE_NEWS_BLOCKLIST = [
    "#shorts",
    "shorts",
    "personal style",
    "style",
    "fashion",
    "behind the scenes",
    "bts",
    "clip",
    "recap",
    "highlight",
    "childhood crush",
    "crush",
    "character spotlight",
    "watch now",
    "exclusive clip",
    "preview clip",
    "kids hut",
    "magical story",
    "father's day",
    "mother's day",
    "lullaby",
    "kids story",
    "rhymes",
    "nursery",
    "moral stories",
    "stories for kids",
    "bedtime stories",
    "kids stories"
]


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

    # Clean up social links, follow links, and divider lines
    if description:
        lines = description.split("\n")
        cleaned_lines = []
        for line in lines:
            line_strip = line.strip()
            if not line_strip:
                cleaned_lines.append("")
                continue
            # Filter divider lines consisting of repeating characters
            if re.match(r"^[-=_*★✿►.]{3,}$", line_strip) or len(set(line_strip)) <= 2:
                continue
            # Filter social links, CTAs
            line_lower = line_strip.lower()
            if "http" in line_lower or "subscribe" in line_lower or "follow" in line_lower or "facebook" in line_lower or "twitter" in line_lower or "instagram" in line_lower or "pinterest" in line_lower or "like us" in line_lower:
                continue
            
            # Remove bullet characters at the beginning of the line
            line_clean = re.sub(r"^[\s★✿►•*#\-_]+", "", line_strip).strip()
            if line_clean:
                cleaned_lines.append(line_clean)
        
        description = "\n".join(cleaned_lines)
        description = re.sub(r"\n{3,}", "\n\n", description).strip()

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
                        title = sanitize_text(entry.title)
                        description = extract_description(entry)

                        # Relevance Filtering using blocklist
                        title_lower = title.lower()
                        desc_lower = description.lower()
                        if any(keyword in title_lower for keyword in YOUTUBE_NEWS_BLOCKLIST) or \
                           any(keyword in desc_lower for keyword in YOUTUBE_NEWS_BLOCKLIST):
                            continue

                        # Extract image thumbnail
                        image_url = None
                        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                            image_url = entry.media_thumbnail[0].get("url")

                        video_id = getattr(entry, "yt_videoid", None)

                        articles.append({
                            "title": title,
                            "url": f"https://youtube.com/watch?v={video_id}" if video_id else getattr(entry, "link", ""),
                            "source": "youtube",
                            "youtube_channel": name,
                            "description": description,
                            "published_at": published_at,
                            "image_url": image_url
                        })

            except Exception as e:
                print("YouTube RSS error:", name, e)

    print("📺 YouTube:", len(articles))
    return articles