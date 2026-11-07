"""Composition root: the one place that wires use cases to concrete infrastructure.

Swapping a technology (e.g. MongoDB -> PostgreSQL, Cloudinary -> S3) means writing
new implementations of the domain ports and changing the constructors here.
Interface code (FastAPI routers, schedulers, scripts) gets use cases from this module.
"""

from functools import lru_cache

from app.application.search.service import SearchService
from app.application.trending.service import TrendingService
from app.config import SEARCH_BACKEND, SEARCH_CATALOG_KINDS
from app.db.mongo import get_db
from app.infrastructure.mongo.atlas_search_index import AtlasSearchIndex
from app.infrastructure.mongo.content_catalog import MongoContentCatalog
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
