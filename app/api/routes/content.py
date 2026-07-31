from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Literal

from app.api.deps import get_current_user, get_optional_user
from app.services import content_service
from app.services.content_service import ContentError

router = APIRouter(
    tags=["Content"]
)


class RatingRequest(BaseModel):
    rating: Literal["Skip", "Timepass", "Go for it", "Perfection"]


class CommentRequest(BaseModel):
    text: str
    parent_id: str | None = None




from app.repositories.content_repository import get_dated_releases_range, get_announced_releases_range

@router.get("/content/releases-range")
async def get_releases_range(start_date: str = Query(...), end_date: str = Query(...)):
    try:
        return await get_dated_releases_range(start_date, end_date)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/content/announced-range")
async def get_announced_range(start_date: str = Query(...), end_date: str = Query(...)):
    try:
        return await get_announced_releases_range(start_date, end_date)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Public Episode/Chapter Detail ---

from app.services.content_lookup import resolve_content_title
from app.db.mongo import get_db

@router.get("/episodes/{content_id}")
async def get_episode_detail(content_id: str):
    db = get_db()
    doc = await db["episodes"].find_one({"_id": content_id})
    if not doc or doc.get("is_deleted"):
        raise HTTPException(status_code=404, detail="Episode not found")

    parent_type = "anime" if doc.get("anime_id") else "tv_series"
    parent_id = doc.get("anime_id") or doc.get("tv_series_id")

    parent_info = await resolve_content_title(parent_type, parent_id) if parent_id else None

    return {
        "episode_number": doc.get("episode_number"),
        "title": doc.get("title"),
        "release_date": doc.get("release_date"),
        "director": doc.get("director"),
        "arc": doc.get("arc"),
        "is_filler": doc.get("is_filler", False),
        "canon_type": doc.get("canon_type"),
        "summary": doc.get("summary"),
        "parent_type": parent_type,
        "parent_id": parent_id,
        "parent_title": parent_info["title"] if parent_info else None,
        "parent_poster": parent_info["poster_image"] if parent_info else None,
    }

@router.get("/chapters/{content_id}")
async def get_chapter_detail(content_id: str):
    db = get_db()
    doc = await db["chapters"].find_one({"_id": content_id})
    if not doc or doc.get("is_deleted"):
        raise HTTPException(status_code=404, detail="Chapter not found")

    manga_id = doc.get("manga_id")
    parent_info = await resolve_content_title("manga", manga_id) if manga_id else None

    return {
        "chapter_number": doc.get("chapter_number"),
        "release_date": doc.get("release_date"),
        "summary": doc.get("summary"),
        "parent_id": manga_id,
        "parent_title": parent_info["title"] if parent_info else None,
        "parent_poster": parent_info["poster_image"] if parent_info else None,
    }


# --- Trending ---

from app.services.trending_service import get_trending_content

@router.get("/content/trending")
async def get_trending(limit: int = 10):
    try:
        return await get_trending_content(limit)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Ratings ---

@router.post("/content/{content_type}/{content_id}/rate")
async def rate_content(
    content_type: str,
    content_id: str,
    payload: RatingRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        return await content_service.rate_content(
            current_user["_id"], content_type, content_id, payload.rating
        )
    except ContentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/content/{content_type}/{content_id}/rating")
async def get_rating(
    content_type: str,
    content_id: str,
    current_user: dict | None = Depends(get_optional_user),
):
    user_id = current_user["_id"] if current_user else None

    try:
        return await content_service.get_content_rating(user_id, content_type, content_id)
    except ContentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete("/content/{content_type}/{content_id}/rate")
async def delete_rating(
    content_type: str,
    content_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        await content_service.remove_rating(current_user["_id"], content_type, content_id)
        return {"status": "ok"}
    except ContentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# --- Watchlist ---

@router.post("/content/{content_type}/{content_id}/watchlist")
async def add_to_watchlist(
    content_type: str,
    content_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        return await content_service.add_watchlist_item(current_user["_id"], content_type, content_id)
    except ContentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete("/content/{content_type}/{content_id}/watchlist")
async def remove_from_watchlist(
    content_type: str,
    content_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        return await content_service.remove_watchlist_item(current_user["_id"], content_type, content_id)
    except ContentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/content/{content_type}/{content_id}/watchlist")
async def check_watchlist(
    content_type: str,
    content_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        return await content_service.check_watchlist_item(current_user["_id"], content_type, content_id)
    except ContentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/watchlist")
async def get_my_watchlist(current_user: dict = Depends(get_current_user)):
    return await content_service.fetch_user_watchlist(current_user["_id"])


# --- Comments ---

@router.post("/content/{content_type}/{content_id}/comments")
async def add_comment(
    content_type: str,
    content_id: str,
    payload: CommentRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        return await content_service.add_comment(
            current_user["_id"], content_type, content_id, payload.text, payload.parent_id
        )
    except ContentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/content/{content_type}/{content_id}/comments")
async def get_comments(content_type: str, content_id: str):
    try:
        return await content_service.fetch_comments(content_type, content_id)
    except ContentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        await content_service.remove_comment(current_user["_id"], comment_id)
        return {"status": "ok"}
    except ContentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# --- Detail Page ---

@router.get("/content/{content_type}/{content_id}")
async def get_content_details(
    content_type: str,
    content_id: str
):
    try:
        return await content_service.fetch_content_details(content_type, content_id)
    except ContentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)