import asyncio
import logging
from app.db.mongo import connect_db, close_db, get_db
from app.backend.ingestion.tmdb_client import get_movie_details, get_tv_details
from app.backend.ingestion.tmdb_mapper import map_movie, map_tv_series
from app.services.cast_reconciliation_service import reconcile_cast, reconcile_directors, reconcile_creators, reconcile_writers
from app.repositories.movie_repository import upsert_movie
from app.repositories.tv_series_repository import upsert_tv_series

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def resync_collection(collection_name: str, get_details_func, map_func, upsert_func):
    db = get_db()
    collection = db[collection_name]
    # We only care about docs that have tmdb_id AND either missing cast or empty cast
    query = {
        "source_metadata.tmdb_id": {"$exists": True},
        "$or": [
            {"cast": {"$exists": False}},
            {"cast": {"$size": 0}}
        ]
    }

    count = await collection.count_documents(query)
    logger.info(f"Found {count} documents to re-sync in {collection_name}")
    
    if count == 0:
        return

    processed = 0
    updated = 0
    failed = 0
    
    cursor = collection.find(query)
    async for doc in cursor:
        tmdb_id = doc.get("source_metadata", {}).get("tmdb_id")
        
        details = await get_details_func(tmdb_id)
        if not details:
            logger.warning(f"Failed to fetch details for {collection_name} tmdb_id={tmdb_id}")
            failed += 1
            continue
            
        mapped_doc = map_func(details)
        if collection_name == "movies":
            mapped_doc["director"] = await reconcile_directors(mapped_doc.get("director", []))
            mapped_doc["writer"] = await reconcile_writers(mapped_doc.get("writers", []))
        else:
            mapped_doc["creators"] = await reconcile_creators(mapped_doc.get("creators", []))
            
        mapped_doc["cast"] = await reconcile_cast(mapped_doc.get("cast", []))
        
        # Upsert
        await upsert_func(mapped_doc)
        
        processed += 1
        updated += 1
        
        if processed % 10 == 0:
            logger.info(f"Re-sync progress ({collection_name}): {processed}/{count}")
            
    logger.info(f"Finished re-syncing {collection_name}. Updated {updated}, Failed {failed}.")


async def main():
    await connect_db()
    try:
        await resync_collection("movies", get_movie_details, map_movie, upsert_movie)
        await resync_collection("tv_series", get_tv_details, map_tv_series, upsert_tv_series)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
