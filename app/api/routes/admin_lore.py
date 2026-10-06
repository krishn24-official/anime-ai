import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import get_current_admin
from app.repositories import lore_repository
from app.schemas.lore import LoreUploadResponse
from app.services import lore_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/lore",
    tags=["Admin - Lore"],
)


@router.post("/upload", response_model=LoreUploadResponse)
async def upload_lore_pdf(
    file: UploadFile = File(...),
    series_id: str = Form(...),
    character_ids: Optional[str] = Form(None),
    current_admin: dict = Depends(get_current_admin),
):
    """
    Admin-only: Upload and ingest a lore PDF for a specific anime/series.
    Clears previous lore chunks for this series and replaces them with new chunks.
    """
    filename = file.filename or "uploaded_lore.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF (.pdf) files are supported.",
        )

    # Parse character_ids (supports JSON array or comma-separated string)
    parsed_character_ids: list[str] = []
    if character_ids:
        try:
            loaded = json.loads(character_ids)
            if isinstance(loaded, list):
                parsed_character_ids = [
                    str(item).strip() for item in loaded if str(item).strip()
                ]
            elif isinstance(loaded, str):
                parsed_character_ids = [
                    s.strip() for s in loaded.split(",") if s.strip()
                ]
        except Exception:
            parsed_character_ids = [
                s.strip() for s in character_ids.split(",") if s.strip()
            ]

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        # Process PDF -> chunk -> embed
        chunks = lore_service.process_lore_pdf(
            file_bytes=file_bytes,
            series_id=series_id,
            character_ids=parsed_character_ids,
            source_file=filename,
        )

        # Clear existing chunks for this series and insert new ones
        await lore_repository.delete_by_series(series_id)
        await lore_repository.insert_chunks(chunks)

        return LoreUploadResponse(
            series_id=series_id,
            chunks_created=len(chunks),
            source_file=filename,
        )

    except ValueError as err:
        logger.warning(f"[admin_lore] Validation error during lore upload: {err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except Exception as err:
        logger.error(f"[admin_lore] Error processing lore PDF upload: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process lore PDF: {err}",
        ) from err


@router.delete("/{series_id}")
async def delete_series_lore(
    series_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    """
    Admin-only: Delete all indexed lore chunks for a given series_id.
    """
    deleted_count = await lore_repository.delete_by_series(series_id)
    return {
        "series_id": series_id,
        "chunks_deleted": deleted_count,
    }


@router.get("/{series_id}/status")
async def get_series_lore_status(
    series_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    """
    Admin-only: Get the indexing status (count of chunks and distinct source files) for a given series_id.
    """
    return await lore_repository.get_series_lore_status(series_id)
