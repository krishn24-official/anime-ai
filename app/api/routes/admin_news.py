from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from app.api.deps import get_current_admin
from app.services import manual_news_service

router = APIRouter(
    prefix="/admin/news",
    tags=["Admin - News"]
)


@router.post("")
async def create_news(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(..., description="Anime, Games, Movies, TV Series"),
    images: list[UploadFile] = File(default=[]),
    current_admin: dict = Depends(get_current_admin),
):
    """
    Admin-only: manually post a news article/leak with optional image
    attachments. Images are uploaded to Cloudinary.
    """

    image_files = []
    for upload in images:
        content = await upload.read()
        if content:
            image_files.append((content, upload.filename or "image.jpg"))

    result, error = await manual_news_service.create_news_post(
        title=title,
        description=description,
        category=category,
        author_id=current_admin["_id"],
        author_name=current_admin.get("display_name") or current_admin.get("username"),
        image_files=image_files,
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    return result


@router.get("/{news_id}")
async def get_news(
    news_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    result = await manual_news_service.fetch_manual_news(news_id)

    if not result:
        raise HTTPException(status_code=404, detail="News post not found")

    return result


@router.put("/{news_id}")
async def update_news(
    news_id: str,
    title: str | None = Form(None),
    description: str | None = Form(None),
    category: str | None = Form(None),
    current_admin: dict = Depends(get_current_admin),
):
    result, error = await manual_news_service.update_news_post(
        news_id=news_id,
        title=title,
        description=description,
        category=category,
    )

    if error:
        status_code = 404 if "not found" in error.lower() else 400
        raise HTTPException(status_code=status_code, detail=error)

    return result


@router.delete("/{news_id}")
async def delete_news(
    news_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    success, error = await manual_news_service.remove_news_post(news_id)

    if not success:
        raise HTTPException(status_code=404, detail=error)

    return {"message": "News post deleted"}