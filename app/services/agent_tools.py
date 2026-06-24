"""
Tool implementations for the AI agent.
Each function is the actual execution of a tool call from Gemini.
"""
import json
from datetime import datetime, timezone

from app.repositories.home_repository import (
    get_today_birthdays,
    get_today_anime_anniversaries,
    get_today_manga_anniversaries,
)
from app.repositories.news_repository import (
    get_latest_news,
    get_news_by_category,
)
from app.repositories.search_repository import (
    search_characters,
    search_anime,
    search_manga,
    search_movies,
    search_tv_series,
    search_organizations,
)
from app.repositories.chat_repository import find_character
from app.repositories.rating_repository import get_top_rated, get_watchlist_counts
from app.services.chat_context_service import build_character_context
from app.services.rating_scale import weight_to_label
from app.db.mongo import get_db


def _serialize(obj):
    """JSON-safe serializer for MongoDB docs."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


async def tool_get_today_birthdays() -> str:
    birthdays = await get_today_birthdays()
    result = [
        {
            "name": b.get("name"),
            "id": str(b.get("_id")),
            "role": b.get("role"),
        }
        for b in birthdays
    ]
    return json.dumps(result, default=_serialize) if result else "No character birthdays today."


async def tool_get_today_events() -> str:
    anime = await get_today_anime_anniversaries()
    manga = await get_today_manga_anniversaries()

    result = {
        "anime_anniversaries": [
            {
                "title": a.get("title", {}).get("english") or a.get("title", {}).get("romaji"),
                "years_ago": a.get("years_ago"),
            }
            for a in anime
        ],
        "manga_anniversaries": [
            {
                "name": m.get("name"),
                "years_ago": m.get("years_ago"),
            }
            for m in manga
        ],
    }

    if not result["anime_anniversaries"] and not result["manga_anniversaries"]:
        return "No anime or manga anniversaries today."

    return json.dumps(result, default=_serialize)


async def tool_get_latest_news(limit: int = 5) -> str:
    limit = min(max(int(limit), 1), 20)
    articles = await get_latest_news(limit=limit)

    result = [
        {
            "title": a.get("title"),
            "category": a.get("category"),
            "summary": a.get("summary") or a.get("description", "")[:200],
            "source": a.get("source"),
            "published_at": a.get("published_at"),
        }
        for a in articles
    ]

    return json.dumps(result, default=_serialize) if result else "No recent news found."


async def tool_get_news_by_category(category: str, limit: int = 5) -> str:
    valid = {"Anime", "Games", "Movies", "TV Series"}

    if category not in valid:
        return f"Invalid category '{category}'. Choose from: {', '.join(valid)}"

    limit = min(max(int(limit), 1), 20)
    articles, _ = await get_news_by_category(category=category, page=1, limit=limit)

    result = [
        {
            "title": a.get("title"),
            "summary": a.get("summary") or a.get("description", "")[:200],
            "source": a.get("source"),
            "published_at": a.get("published_at"),
        }
        for a in articles
    ]

    return json.dumps(result, default=_serialize) if result else f"No recent {category} news found."


async def tool_search_content(query: str) -> str:
    characters = await search_characters(query)
    anime = await search_anime(query)
    manga = await search_manga(query)
    movies = await search_movies(query)
    tv_series = await search_tv_series(query)
    organizations = await search_organizations(query)

    result = {
        "characters": [{"name": c.get("name"), "id": str(c.get("_id"))} for c in characters],
        "anime": [{"title": a.get("title", {}).get("english") or a.get("title", {}).get("romaji"), "id": str(a.get("_id"))} for a in anime],
        "manga": [{"name": m.get("name"), "id": str(m.get("_id"))} for m in manga],
        "movies": [{"title": mv.get("title"), "id": str(mv.get("_id"))} for mv in movies],
        "tv_series": [{"title": tv.get("title"), "id": str(tv.get("_id"))} for tv in tv_series],
        "organizations": [{"name": o.get("name"), "id": str(o.get("id"))} for o in organizations],
    }

    total = sum(len(v) for v in result.values())

    if total == 0:
        return f"No results found for '{query}'."

    return json.dumps(result, default=_serialize)


async def tool_get_character_info(name: str) -> str:
    """
    Looks up a character by exact name first.
    If not found, falls back to search to find close matches.
    """
    # Guard: if the input looks like a question rather than a name, reject early
    question_words = {"what", "which", "who", "how", "when", "where", "tell", "show", "list", "get"}
    first_word = name.strip().lower().split()[0] if name.strip() else ""
    if first_word in question_words or len(name.split()) > 5:
        return (
            f"'{name}' does not look like a character name. "
            "Please use get_content_trends for ratings/trending questions, "
            "or get_latest_news for news questions."
        )

    character = await find_character(name)

    if character:
        context = await build_character_context(character)
        return json.dumps(context, default=_serialize)

    # Fallback: try search
    characters = await search_characters(name)

    if characters:
        suggestions = [c.get("name") for c in characters[:3]]
        return (
            f"Character '{name}' not found by exact name. "
            f"Did you mean one of these? {', '.join(suggestions)}. "
            f"Try calling get_character_info with the exact name."
        )

    return f"Character '{name}' not found in the database."


async def tool_get_content_trends(
    content_type: str | None = None,
    trend_type: str = "ratings",
    limit: int = 5,
) -> str:
    """
    Returns top-rated or most-watchlisted content.
    trend_type: 'ratings' or 'watchlist'
    content_type: optional filter — 'anime', 'manga', 'movie', 'tv_series'
    """
    limit = min(max(int(limit), 1), 20)

    valid_types = {"anime", "manga", "movie", "tv_series"}
    if content_type and content_type not in valid_types:
        return f"Invalid content_type '{content_type}'. Choose from: {', '.join(valid_types)}"

    db = get_db()

    if trend_type == "watchlist":
        results = await get_watchlist_counts(content_type=content_type, limit=limit)

        if not results:
            return "No watchlist data available yet."

        enriched = []
        for r in results:
            ctype = r["_id"]["content_type"]
            cid = r["_id"]["content_id"]

            # Fetch title from the right collection
            collection_map = {
                "anime": "anime", "manga": "manga",
                "movie": "movies", "tv_series": "tv_series",
            }
            col = collection_map.get(ctype)
            doc = await db[col].find_one({"_id": cid}, {"title": 1, "name": 1}) if col else None
            title = (
                (doc.get("title") if isinstance(doc.get("title"), str) else
                 doc.get("title", {}).get("english") or doc.get("title", {}).get("romaji"))
                if doc else cid
            ) or doc.get("name") if doc else cid

            enriched.append({
                "content_type": ctype,
                "content_id": cid,
                "title": title,
                "watchlist_count": r["count"],
            })

        return json.dumps(enriched, default=_serialize)

    else:
        # ratings (default)
        results = await get_top_rated(content_type=content_type, limit=limit)

        if not results:
            return "No ratings data available yet."

        enriched = []
        for r in results:
            ctype = r["_id"]["content_type"]
            cid = r["_id"]["content_id"]
            avg_weight = round(r["average_weight"], 2)

            collection_map = {
                "anime": "anime", "manga": "manga",
                "movie": "movies", "tv_series": "tv_series",
            }
            col = collection_map.get(ctype)
            doc = await db[col].find_one({"_id": cid}, {"title": 1, "name": 1}) if col else None
            title = (
                (doc.get("title") if isinstance(doc.get("title"), str) else
                 doc.get("title", {}).get("english") or doc.get("title", {}).get("romaji"))
                if doc else cid
            ) or (doc.get("name") if doc else cid)

            enriched.append({
                "content_type": ctype,
                "content_id": cid,
                "title": title or cid,
                "average_rating": weight_to_label(avg_weight),
                "average_weight": avg_weight,
                "rating_count": r["count"],
            })

        return json.dumps(enriched, default=_serialize)


async def tool_get_organization_info(name: str) -> str:
    db = get_db()
    org = await db["organizations"].find_one({
        "name": {"$regex": f"^{name}$", "$options": "i"},
        "is_deleted": {"$ne": True}
    })
    if not org:
        cursor = db["organizations"].find({
            "name": {"$regex": name, "$options": "i"},
            "is_deleted": {"$ne": True}
        })
        orgs = await cursor.to_list(1)
        if orgs:
            org = orgs[0]

    if not org:
        return f"Organization '{name}' not found in the database."

    from app.services.organization_service import fetch_organization_details
    details = await fetch_organization_details(str(org["_id"]))
    if not details:
        return f"Could not fetch details for organization '{name}'."

    return json.dumps(details, default=_serialize)


# --- Tool dispatcher ---
TOOL_REGISTRY = {
    "get_today_birthdays": tool_get_today_birthdays,
    "get_today_events": tool_get_today_events,
    "get_latest_news": tool_get_latest_news,
    "get_news_by_category": tool_get_news_by_category,
    "search_content": tool_search_content,
    "get_character_info": tool_get_character_info,
    "get_content_trends": tool_get_content_trends,
    "get_organization_info": tool_get_organization_info,
}


async def execute_tool(tool_name: str, tool_args: dict) -> str:
    fn = TOOL_REGISTRY.get(tool_name)

    if not fn:
        return f"Unknown tool: {tool_name}"

    try:
        return await fn(**tool_args)
    except Exception as e:
        return f"Tool '{tool_name}' error: {e}"