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

from app.api.routes.manga import (
    router as manga_router
)

from app.api.routes.health import (
    router as health_router
)

from app.api.routes.home import (
    router as home_router
)

from app.api.routes.event import (
    router as event_router
)

from app.api.routes.search import (
    router as search_router
)

from app.api.routes.chat import (
    router as chat_router
)

from app.api.routes.news import (
    router as news_router
)

from app.api.routes.auth import (
    router as auth_router
)

from app.api.routes.movies import (
    router as movies_router
)

from app.api.routes.tv_series import (
    router as tv_series_router
)

from app.api.routes.content import (
    router as content_router
)

from app.api.routes.agent import (
    router as agent_router
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

api_router.include_router(
    manga_router
)

api_router.include_router(
    health_router
)

api_router.include_router(
    home_router
)

api_router.include_router(
    event_router
)

api_router.include_router(
    search_router
)

api_router.include_router(
    chat_router
)

api_router.include_router(
    news_router
)

api_router.include_router(
    auth_router
)

api_router.include_router(
    movies_router
)

api_router.include_router(
    tv_series_router
)

api_router.include_router(
    content_router
)

api_router.include_router(
    agent_router
)