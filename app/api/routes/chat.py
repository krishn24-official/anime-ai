from fastapi import APIRouter

from app.schemas.chat_schema import ChatRequest

from app.services.chat_service import (
    process_chat_message
)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)


@router.post("")
async def chat(
    payload: ChatRequest
):

    return await (
        process_chat_message(
            payload.message,
            payload.image_base64,
            payload.image_media_type
        )
    )