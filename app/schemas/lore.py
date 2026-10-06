from datetime import datetime, timezone
from pydantic import BaseModel, Field


class LoreChunk(BaseModel):
    chunk_id: str
    series_id: str
    character_ids: list[str] = Field(default_factory=list)
    chunk_text: str
    embedding_vector: list[float]
    source_file: str
    section_title: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LoreUploadResponse(BaseModel):
    series_id: str
    chunks_created: int
    source_file: str


class LoreQueryResult(BaseModel):
    chunk_text: str
    score: float
    section_title: str | None = None
    series_id: str
