from fastapi import APIRouter

from app.api.routes.character import (
    router as character_router
)

from app.api.routes.relationship import (
    router as relationship_router
)

from app.api.routes.anime import (
    router as anime_router
)

api_router = APIRouter()

api_router.include_router(
    character_router
)

api_router.include_router(
    relationship_router
)

api_router.include_router(
    anime_router
)