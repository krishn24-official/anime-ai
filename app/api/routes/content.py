from fastapi import APIRouter, Depends, HTTPException
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