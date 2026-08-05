import asyncio
import logging
from app.db.mongo import connect_db, close_db, get_db
from app.services.cast_reconciliation_service import reconcile_writers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_writers(collection_name: str):
    db = get_db()
    collection = db[collection_name]
    
    # We want to find docs where the old 'writers' field exists and contains at least one string element.
    # The old shape is a list of strings: ["Christopher Nolan", "Emma Thomas"]
    query = {
        "writers": {
            "$elemMatch": {
                "$type": "string"
            }
        }
    }

    count = await collection.count_documents(query)
    logger.info(f"Found {count} documents to backfill in {collection_name} for writers -> writer")
    
    if count == 0:
        return

    processed = 0
    updated = 0
    
    cursor = collection.find(query)
    async for doc in cursor:
        doc_id = doc["_id"]
        original_data = doc.get("writers", [])
        
        # Convert legacy string format to the dict format expected by the reconciliation functions
        raw_to_reconcile = []
        for entry in original_data:
            if isinstance(entry, str):
                raw_to_reconcile.append({
                    "tmdb_person_id": None,
                    "name": entry,
                    "profile_image": None
                })
            elif isinstance(entry, dict):
                raw_to_reconcile.append(entry)
                
        reconciled = await reconcile_writers(raw_to_reconcile)
        
        await collection.update_one(
            {"_id": doc_id},
            {"$set": {"writer": reconciled}}
        )
        
        processed += 1
        updated += 1
        
        if processed % 50 == 0:
            logger.info(f"Backfill progress ({collection_name}): {processed}/{count}")
            
    logger.info(f"Finished backfilling {collection_name}. Updated {updated} documents.")

async def main():
    await connect_db()
    try:
        await backfill_writers("movies")
        await backfill_writers("tv_series")
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
