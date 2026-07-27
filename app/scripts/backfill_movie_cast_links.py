import asyncio
import logging
from app.db.mongo import connect_db, close_db, get_db
from app.services.cast_reconciliation_service import reconcile_cast

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_collection(collection_name: str):
    db = get_db()
    collection = db[collection_name]
    
    # We only care about docs that have at least one cast member missing 'actor_id'
    # The old shape is just 'name', 'character', 'profile_image'.
    # A reconciled cast member has 'actor_id'.
    # We can query where cast exists, and inside it there's an element without 'actor_id'.
    query = {
        "cast": {
            "$elemMatch": {
                "actor_id": {"$exists": False}
            }
        }
    }

    count = await collection.count_documents(query)
    logger.info(f"Found {count} documents to backfill in {collection_name}")
    
    if count == 0:
        return

    processed = 0
    updated = 0
    
    cursor = collection.find(query)
    async for doc in cursor:
        doc_id = doc["_id"]
        original_cast = doc.get("cast", [])
        
        # In the old shape, tmdb_person_id is missing, but resolve_or_create_actor uses it to fetch TMDB.
        # Wait, if they were ingested BEFORE we added tmdb_person_id to tmdb_mapper,
        # they only have "name", "character", "profile_image".
        # resolve_or_create_actor gracefully falls back to creating the actor with just name and image
        # if tmdb_person_id is missing!
        
        reconciled = await reconcile_cast(original_cast)
        
        await collection.update_one(
            {"_id": doc_id},
            {"$set": {"cast": reconciled}}
        )
        
        processed += 1
        updated += 1
        
        if processed % 50 == 0:
            logger.info(f"Backfill progress ({collection_name}): {processed}/{count}")
            
    logger.info(f"Finished backfilling {collection_name}. Updated {updated} documents.")


async def main():
    await connect_db()
    try:
        await backfill_collection("movies")
        await backfill_collection("tv_series")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
