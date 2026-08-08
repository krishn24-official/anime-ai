import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.db.mongo import get_db, connect_db
from app.backend.ingestion.tmdb_client import (
    discover_movies,
    discover_tv,
    get_movie_details,
    get_tv_details
)
from app.backend.ingestion.tmdb_mapper import map_movie, map_tv_series
from app.repositories.movie_repository import upsert_movie
from app.repositories.tv_series_repository import upsert_tv_series
from app.services.cast_reconciliation_service import (
    reconcile_cast,
    reconcile_directors,
    reconcile_creators,
    reconcile_writers
)

from app.backend.ingestion.anime.fetch_all import AniListRateLimiter, anilist_request
from app.backend.transformers.anime_transformer import transform_anime
from app.backend.ingestion.anime.anilist_resolvers import (
    resolve_or_create_character,
    resolve_or_create_voice_actor
)

logger = logging.getLogger(__name__)

# AniList query that mirrors the exact shape from fetch_all, but tailored for incremental ID-based fetching
ANIME_INCREMENTAL_QUERY = """
query ($page: Int, $perPage: Int, $season: MediaSeason, $seasonYear: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      hasNextPage
    }
    media(type: ANIME, sort: ID_DESC, season: $season, seasonYear: $seasonYear) {
      id
      title {
        english
        romaji
        native
      }
      synonyms
      format
      status
      genres
      season
      seasonYear
      source
      episodes
      duration
      averageScore
      coverImage {
        large
      }
      bannerImage
      startDate {
        year
        month
        day
      }
      endDate {
        year
        month
        day
      }
      studios {
        nodes {
          name
        }
      }
      characters(sort: ROLE, perPage: 25) {
        edges {
          role
          node {
            id
            name {
              full
              native
            }
            image {
              large
            }
            gender
            description
            age
            dateOfBirth {
              day
              month
            }
          }
          voiceActors(language: JAPANESE) {
            id
            name {
              full
              native
            }
            image {
              large
            }
            description
            gender
            dateOfBirth {
              year
              month
              day
            }
          }
        }
      }
    }
  }
}
"""

async def discover_new_movies():
    """Discover newly released or announced movies on TMDB."""
    now = datetime.now(timezone.utc)
    gte_date = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    lte_date = (now + timedelta(days=120)).strftime("%Y-%m-%d")

    db = get_db()
    movies_collection = db["movies"]
    
    saved_count = 0
    skipped_count = 0
    failed_count = 0
    
    max_pages = 50  # Hard failsafe
    current_page = 1
    
    logger.info(f"Starting TMDB movie discovery window: {gte_date} to {lte_date}")
    
    while current_page <= max_pages:
        response = await discover_movies(
            page=current_page,
            sort_by="primary_release_date.desc",
            **{
                "primary_release_date.gte": gte_date,
                "primary_release_date.lte": lte_date,
                "with_release_type": "2|3"
            }
        )
        
        results = response.get("results", [])
        if not results:
            break
            
        for item in results:
            tmdb_id = item["id"]
            
            # 1. Existence check by tmdb_id
            existing_by_tmdb = await movies_collection.find_one({
                "source_metadata.tmdb_id": tmdb_id,
                "is_deleted": {"$ne": True}
            })
            
            if existing_by_tmdb:
                skipped_count += 1
                continue
                
            # 2. Fetch full details for new entries
            details = await get_movie_details(tmdb_id)
            if not details:
                logger.error(f"[TMDB Movies] Could not fetch details for {tmdb_id}")
                failed_count += 1
                continue
                
            title = details.get("title")
            if not title:
                failed_count += 1
                continue
                
            # 3. Existence check by title (for manual entries missing tmdb_id)
            existing_by_title = await movies_collection.find_one({
                "title": title,
                "is_deleted": {"$ne": True}
            })
            if existing_by_title:
                skipped_count += 1
                continue
                
            # 4. Map and ingest (exact same path as bulk importer)
            doc = map_movie(details, max_cast=10)
            
            # Ensure unique _id (same logic as ingest_tmdb_movies.py)
            movie_db_id = doc["_id"]
            base_movie_id = movie_db_id
            counter = 1
            while await movies_collection.find_one({"_id": movie_db_id}):
                movie_db_id = f"{base_movie_id}_{counter}"
                counter += 1
                
            doc["_id"] = movie_db_id
            doc["source_metadata"]["source"] = "tmdb"
            doc["source_metadata"]["created_by"] = "daily_discovery"
            doc["source_metadata"]["created_at"] = datetime.now(timezone.utc)
            
            doc["director"] = await reconcile_directors(doc.get("director", []))
            doc["writer"] = await reconcile_writers(doc.get("writers", []))
            doc["cast"] = await reconcile_cast(doc.get("cast", []))
            
            # upsert_movie does the cross-collection duplicate check inside
            await upsert_movie(doc)
            saved_count += 1
            
            # Be gentle on rate limits
            await asyncio.sleep(0.05)
            
        total_pages = response.get("total_pages", 1)
        if current_page >= total_pages:
            break
            
        current_page += 1
        
    if current_page > max_pages:
        logger.warning(f"TMDB Movies daily discovery hit the {max_pages}-page failsafe cap! Real results may have been truncated.")
        
    return {"saved": saved_count, "skipped": skipped_count, "failed": failed_count}

async def discover_new_tv():
    """Discover newly released or announced TV series on TMDB."""
    now = datetime.now(timezone.utc)
    gte_date = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    lte_date = (now + timedelta(days=120)).strftime("%Y-%m-%d")

    db = get_db()
    tv_collection = db["tv_series"]
    
    saved_count = 0
    skipped_count = 0
    failed_count = 0
    
    max_pages = 50
    current_page = 1
    
    logger.info(f"Starting TMDB TV discovery window: {gte_date} to {lte_date}")
    
    while current_page <= max_pages:
        response = await discover_tv(
            page=current_page,
            sort_by="first_air_date.desc",
            **{
                "first_air_date.gte": gte_date,
                "first_air_date.lte": lte_date
            }
        )
        
        results = response.get("results", [])
        if not results:
            break
            
        for item in results:
            tmdb_id = item["id"]
            
            existing_by_tmdb = await tv_collection.find_one({
                "source_metadata.tmdb_id": tmdb_id,
                "is_deleted": {"$ne": True}
            })
            
            if existing_by_tmdb:
                skipped_count += 1
                continue
                
            details = await get_tv_details(tmdb_id)
            if not details:
                logger.error(f"[TMDB TV] Could not fetch details for {tmdb_id}")
                failed_count += 1
                continue
                
            title = details.get("name")
            if not title:
                failed_count += 1
                continue
                
            existing_by_title = await tv_collection.find_one({
                "title": title,
                "is_deleted": {"$ne": True}
            })
            if existing_by_title:
                skipped_count += 1
                continue
                
            doc = map_tv_series(details, max_cast=10)
            
            tv_db_id = doc["_id"]
            base_tv_id = tv_db_id
            counter = 1
            while await tv_collection.find_one({"_id": tv_db_id}):
                tv_db_id = f"{base_tv_id}_{counter}"
                counter += 1
                
            doc["_id"] = tv_db_id
            doc["source_metadata"]["source"] = "tmdb"
            doc["source_metadata"]["created_by"] = "daily_discovery"
            doc["source_metadata"]["created_at"] = datetime.now(timezone.utc)
            
            doc["creators"] = await reconcile_creators(doc.get("creators", []))
            doc["cast"] = await reconcile_cast(doc.get("cast", []))
            
            await upsert_tv_series(doc)
            saved_count += 1
            
            await asyncio.sleep(0.05)
            
        total_pages = response.get("total_pages", 1)
        if current_page >= total_pages:
            break
            
        current_page += 1
        
    if current_page > max_pages:
        logger.warning(f"TMDB TV daily discovery hit the {max_pages}-page failsafe cap! Real results may have been truncated.")
        
    return {"saved": saved_count, "skipped": skipped_count, "failed": failed_count}

def get_seasons(now: datetime) -> list[tuple[str, int]]:
    """Determine the current and next anime season based on the date."""
    year = now.year
    month = now.month
    
    if 1 <= month <= 3:
        current = ("WINTER", year)
        next_season = ("SPRING", year)
    elif 4 <= month <= 6:
        current = ("SPRING", year)
        next_season = ("SUMMER", year)
    elif 7 <= month <= 9:
        current = ("SUMMER", year)
        next_season = ("FALL", year)
    else:
        current = ("FALL", year)
        next_season = ("WINTER", year + 1)
        
    return [current, next_season]

async def process_anilist_season(
    client: httpx.AsyncClient, 
    limiter: AniListRateLimiter, 
    season: str, 
    season_year: int, 
    last_seen_id: int, 
    db
):
    saved_count = 0
    skipped_count = 0
    failed_count = 0
    highest_seen = last_seen_id
    
    anime_collection = db["anime"]
    
    page = 1
    has_next_page = True
    
    logger.info(f"Starting AniList discovery for {season} {season_year}")
    
    while has_next_page:
        data = await anilist_request(
            client, limiter, ANIME_INCREMENTAL_QUERY, 
            {
                "page": page, 
                "perPage": 50, 
                "season": season, 
                "seasonYear": season_year
            }
        )
        
        if not data:
            break
            
        page_info = data.get("data", {}).get("Page", {}).get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        media_list = data.get("data", {}).get("Page", {}).get("media", [])
        
        if not media_list:
            break
            
        for item in media_list:
            anilist_id = item["id"]
            
            if anilist_id <= last_seen_id:
                # We have reached old territory. Since results are ID_DESC, everything from here on is old.
                has_next_page = False
                break
                
            if anilist_id > highest_seen:
                highest_seen = anilist_id
                
            # Double-check DB (failsafe)
            existing_by_id = await anime_collection.find_one({
                "source_metadata.anilist_id": anilist_id,
                "is_deleted": {"$ne": True}
            })
            
            if existing_by_id:
                skipped_count += 1
                continue
                
            # Process new Anime and Characters
            try:
                doc = transform_anime(item)
                anime_db_id = doc["_id"]
                base_anime_id = anime_db_id
                
                # Check for slug collision
                existing_by_slug = await anime_collection.find_one({"_id": anime_db_id})
                if existing_by_slug:
                    # Append anilist_id if slug taken
                    anime_db_id = f"{base_anime_id}_{anilist_id}"
                    
                doc["_id"] = anime_db_id
                
                # Process Characters & VAs
                characters_data = item.get("characters", {}).get("edges", [])
                for edge in characters_data:
                    char_node = edge.get("node")
                    if not char_node:
                        continue
                        
                    role = edge.get("role")
                    va_ids = []
                    voice_actors = edge.get("voiceActors", [])
                    if voice_actors:
                        va_id = await resolve_or_create_voice_actor(voice_actors[0])
                        if va_id:
                            va_ids = [va_id]
                            
                    await resolve_or_create_character(
                        char_node=char_node,
                        anime_id=anime_db_id,
                        role=role,
                        voice_actor_ids=va_ids
                    )
                
                # Check for cross-collection duplicates before insert
                from app.services.duplicate_detection_service import check_for_duplicate, apply_reciprocal_duplicate_flag
                dup = await check_for_duplicate(doc, "anime")
                if dup:
                    doc["possible_duplicate_of"] = dup
                    await apply_reciprocal_duplicate_flag(doc["_id"], "anime", dup)
                    logger.info(f"Possible duplicate detected for anime: '{doc.get('title', {}).get('english')}' ({doc['_id']})")
                    
                await anime_collection.insert_one(doc)
                saved_count += 1
                
            except Exception as e:
                logger.error(f"[AniList] Failed to process {item.get('title', {}).get('romaji')}: {e}")
                failed_count += 1
                
        page += 1
        
    return {
        "saved": saved_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "highest_seen": highest_seen
    }

async def discover_new_anime():
    """Discover newly added Anime from AniList for current and next seasons."""
    db = get_db()
    checkpoints = db["sync_checkpoints"]
    
    checkpoint = await checkpoints.find_one({"_id": "anilist_daily_discovery"})
    last_seen_id = checkpoint.get("last_seen_anilist_media_id", 0) if checkpoint else 0
    
    limiter = AniListRateLimiter()
    now = datetime.now(timezone.utc)
    seasons = get_seasons(now)
    
    total_saved = 0
    total_skipped = 0
    total_failed = 0
    overall_highest_seen = last_seen_id
    
    async with httpx.AsyncClient() as client:
        for season, season_year in seasons:
            res = await process_anilist_season(client, limiter, season, season_year, last_seen_id, db)
            total_saved += res["saved"]
            total_skipped += res["skipped"]
            total_failed += res["failed"]
            if res["highest_seen"] > overall_highest_seen:
                overall_highest_seen = res["highest_seen"]
                
    if overall_highest_seen > last_seen_id:
        await checkpoints.update_one(
            {"_id": "anilist_daily_discovery"},
            {"$set": {"last_seen_anilist_media_id": overall_highest_seen}},
            upsert=True
        )
        
    return {"saved": total_saved, "skipped": total_skipped, "failed": total_failed}

async def run_daily_discovery():
    """Run all discovery jobs and log a summary."""
    logger.info("Starting Daily Discovery Sync...")
    
    movies_res = await discover_new_movies()
    tv_res = await discover_new_tv()
    anime_res = await discover_new_anime()
    
    logger.info(
        f"Daily Discovery Sync Complete.\n"
        f"Movies -> Saved: {movies_res['saved']}, Skipped: {movies_res['skipped']}, Failed: {movies_res['failed']}\n"
        f"TV     -> Saved: {tv_res['saved']}, Skipped: {tv_res['skipped']}, Failed: {tv_res['failed']}\n"
        f"Anime  -> Saved: {anime_res['saved']}, Skipped: {anime_res['skipped']}, Failed: {anime_res['failed']}"
    )
    
    return {
        "movies": movies_res,
        "tv_series": tv_res,
        "anime": anime_res
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    async def main():
        await connect_db()
        await run_daily_discovery()
    asyncio.run(main())
