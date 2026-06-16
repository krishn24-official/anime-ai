from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    image_base64: str | None = None
    image_media_type: str | None = None