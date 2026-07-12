from datetime import datetime, timezone, timedelta
from app.repositories.trending_repository import (
    upsert_trending,
    remove_trending,
    get_active_trending,
    record_mention,
    get_mention_counts,
    get_search_counts
)
from app.services.title_matcher import find_matches
from app.services.content_lookup import resolve_content_title
from app.services.cloudinary_service import upload_image_from_bytes

MIN_SEARCH_THRESHOLD = 15
RELATIVE_MULTIPLIER = 2.0

async def set_manual_trending(
    content_type: str,
    content_id: str,
    admin_id: str,
    note: str | None = None,
    expires_at: datetime | None = None,
    image_bytes: bytes | None = None
) -> bool:
    doc_info = await resolve_content_title(content_type, content_id)
    if not doc_info:
        return False
        
    custom_poster = None
    if image_bytes:
        url = await upload_image_from_bytes(
            image_bytes,
            folder="entertainment_hub/trending"
        )
        if url:
            custom_poster = url
        
    return await upsert_trending(
        content_type=content_type,
        content_id=content_id,
        source="manual",
        reason="Editor's Pick",
        score=1000.0,
        pinned=True,
        set_by=admin_id,
        note=note,
        expires_at=expires_at,
        custom_poster=custom_poster
    )

async def remove_manual_trending(content_type: str, content_id: str):
    await remove_trending(content_type, content_id)

async def get_trending_content(limit: int = 10):
    entries = await get_active_trending(limit)
    enriched = []
    
    for entry in entries:
        ctype = entry["content_type"]
        cid = entry["content_id"]
        doc_info = await resolve_content_title(ctype, cid)
        
        title = doc_info["title"] if doc_info else cid
        poster = entry.get("custom_poster") or (doc_info["poster_image"] if doc_info else None)
        
        enriched.append({
            "content_type": ctype,
            "content_id": cid,
            "title": title,
            "poster_image": poster,
            "reason": entry.get("reason"),
            "pinned": entry.get("pinned", False),
            "set_at": entry.get("computed_at")
        })
        
    return enriched

async def scan_article_for_mentions(article: dict, alias_index: list):
    title = article.get("title", "")
    desc = article.get("description", "")
    text = f"{title} {desc[:2000]}"
    
    matches = find_matches(text, alias_index)
    news_id = str(article.get("_id"))
    
    for alias, ctype, cid in matches:
        await record_mention(ctype, cid, news_id, alias)

async def recompute_news_trending(hours: int = 48) -> dict:
    counts = await get_mention_counts(hours=hours)
    updated = 0
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=hours)
    
    for item in counts:
        ctype = item["content_type"]
        cid = item["content_id"]
        count = item["mention_count"]
        
        reason = f"Mentioned in {count} article{'s' if count != 1 else ''} this week"
        
        success = await upsert_trending(
            content_type=ctype,
            content_id=cid,
            source="news",
            reason=reason,
            score=float(count),
            pinned=False,
            expires_at=expires
        )
        if success:
            updated += 1
            
    return {"trending_updated": updated}

async def recompute_search_trending(hours: int = 3) -> dict:
    counts = await get_search_counts(hours=hours)
    if not counts:
        return {"evaluated": 0, "qualified": 0, "threshold_used": MIN_SEARCH_THRESHOLD}
        
    avg_count = sum(item["distinct_searcher_count"] for item in counts) / len(counts)
    qualifying_threshold = max(MIN_SEARCH_THRESHOLD, avg_count * RELATIVE_MULTIPLIER)
    
    updated = 0
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=hours)
    
    for item in counts:
        ctype = item["content_type"]
        cid = item["content_id"]
        count = item["distinct_searcher_count"]
        
        if count >= qualifying_threshold:
            reason = f"Searched by {count} people recently"
            
            success = await upsert_trending(
                content_type=ctype,
                content_id=cid,
                source="search",
                reason=reason,
                score=float(count),
                pinned=False,
                expires_at=expires
            )
            if success:
                updated += 1
                
    summary = {
        "evaluated": len(counts),
        "qualified": updated,
        "threshold_used": qualifying_threshold
    }
    print(f"[trending_service] search trending recompute: {summary}")
    return summary


