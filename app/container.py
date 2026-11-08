"""Composition root: the one place that wires use cases to concrete infrastructure.

Swapping a technology (e.g. MongoDB -> PostgreSQL, Cloudinary -> S3) means writing
new implementations of the domain ports and changing the constructors here.
Interface code (FastAPI routers, schedulers, scripts) gets use cases from this module.
"""

from functools import lru_cache

from app.application.guide.service import GuideService
from app.application.home.service import HomeService
from app.application.llm.service import FallbackChatModel
from app.application.lore.rebuild import LoreRebuildService
from app.application.recommendations.service import RecommendationService
from app.application.search.service import SearchService
from app.application.trending.service import TrendingService
from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL_NAME,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_PROVIDERS,
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    NEWS_SEMANTIC_DEDUP,
    SEARCH_BACKEND,
    SEARCH_CATALOG_KINDS,
    TMDB_API_KEY,
)
from app.db.mongo import get_db
from app.infrastructure.embeddings.threaded_embedder import ThreadedEmbedder
from app.infrastructure.external.anilist_recommendations import AniListRecommendations
from app.infrastructure.external.tmdb_recommendations import TmdbRecommendations
from app.infrastructure.llm.gemini_model import GeminiChatModel
from app.infrastructure.llm.openai_compatible_model import GROQ_URL, MISTRAL_URL, OpenAICompatibleChatModel
from app.infrastructure.mongo.atlas_search_index import AtlasSearchIndex
from app.infrastructure.mongo.chapter_guide import MongoChapterGuide
from app.infrastructure.mongo.content_catalog import MongoContentCatalog
from app.infrastructure.mongo.hero_source import MongoHeroSource
from app.infrastructure.mongo.lore_rebuild_stores import MongoEpisodeCatalog, MongoLoreStore
from app.infrastructure.wiki.fandom_episode_source import FandomEpisodeSource
from app.infrastructure.mongo.recommendation_catalog import MongoRecommendationCatalog
from app.infrastructure.mongo.regex_search_index import MongoRegexSearchIndex
from app.infrastructure.mongo.search_catalog import MongoSearchCatalog
from app.infrastructure.mongo.trending_repository import (
    MongoTrendingRepository,
    MongoTrendingSignalRepository,
)
from app.infrastructure.search.fallback_index import FallbackSearchIndex
from app.infrastructure.storage.cloudinary_storage import CloudinaryImageStorage
from app.services.title_matcher import find_matches


@lru_cache(maxsize=None)
def content_catalog() -> MongoContentCatalog:
    return MongoContentCatalog(get_db)


@lru_cache(maxsize=None)
def image_storage() -> CloudinaryImageStorage:
    return CloudinaryImageStorage()


@lru_cache(maxsize=None)
def trending_service() -> TrendingService:
    return TrendingService(
        entries=MongoTrendingRepository(get_db),
        signals=MongoTrendingSignalRepository(get_db),
        catalog=content_catalog(),
        images=image_storage(),
        find_matches=find_matches,
    )


def search_catalog_enabled() -> bool:
    """Whether the Atlas `search_catalog` is used (and therefore kept in sync)."""
    return SEARCH_BACKEND != "regex"


@lru_cache(maxsize=None)
def search_catalog() -> MongoSearchCatalog:
    return MongoSearchCatalog(get_db, SEARCH_CATALOG_KINDS)


@lru_cache(maxsize=None)
def search_service() -> SearchService:
    regex_index = MongoRegexSearchIndex(get_db)
    if not search_catalog_enabled():
        return SearchService(regex_index)
    atlas_index = AtlasSearchIndex(get_db, SEARCH_CATALOG_KINDS)
    return SearchService(FallbackSearchIndex(atlas_index, regex_index))


@lru_cache(maxsize=None)
def home_service() -> HomeService:
    return HomeService(MongoHeroSource(get_db))


@lru_cache(maxsize=None)
def headline_embedder() -> ThreadedEmbedder | None:
    """Embeddings for news de-duplication, or None when disabled."""
    if not NEWS_SEMANTIC_DEDUP:
        return None
    from app.services.lore_service import lore_embedder  # one shared model in memory

    return ThreadedEmbedder(lore_embedder.embed_chunks)


@lru_cache(maxsize=None)
def recommendation_service() -> RecommendationService:
    return RecommendationService(
        search=search_service(),
        catalog=MongoRecommendationCatalog(get_db),
        sources={
            "anime": AniListRecommendations("ANIME"),
            "manga": AniListRecommendations("MANGA"),
            "movie": TmdbRecommendations(TMDB_API_KEY, "movie"),
            "tv_series": TmdbRecommendations(TMDB_API_KEY, "tv_series"),
        },
    )


@lru_cache(maxsize=None)
def guide_service() -> GuideService:
    return GuideService(MongoChapterGuide(get_db))


@lru_cache(maxsize=None)
def chat_model() -> FallbackChatModel:
    """Gemini -> Groq -> Mistral (order from LLM_PROVIDERS); providers without a key are left out."""
    available = {
        "gemini": (GEMINI_API_KEY, lambda: GeminiChatModel(GEMINI_API_KEY, GEMINI_MODEL_NAME)),
        "groq": (GROQ_API_KEY, lambda: OpenAICompatibleChatModel("groq", GROQ_URL, GROQ_API_KEY, GROQ_MODEL)),
        "mistral": (MISTRAL_API_KEY, lambda: OpenAICompatibleChatModel("mistral", MISTRAL_URL, MISTRAL_API_KEY, MISTRAL_MODEL)),
    }
    models = [build() for name in LLM_PROVIDERS if name in available for key, build in [available[name]] if key]
    return FallbackChatModel(models)


def lore_rebuild_service() -> LoreRebuildService:
    """Used by app/scripts/rebuild_lore.py; embeds with the same model lore search queries use."""
    from app.services.lore_service import lore_embedder

    return LoreRebuildService(
        catalog=MongoEpisodeCatalog(get_db),
        source=FandomEpisodeSource(),
        embedder=ThreadedEmbedder(lore_embedder.embed_chunks),
        store=MongoLoreStore(get_db),
    )
