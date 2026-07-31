import asyncio
import logging
from app.db.mongo import connect_db, close_db, get_db
from app.services.cast_reconciliation_service import reconcile_directors, reconcile_creators

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_collection(collection_name: str, field_name: str, reconcile_func):
    db = get_db()
    collection = db[collection_name]
    
    # We want to find docs where the field exists and contains at least one string element.
    # The old shape is a list of strings: ["Christopher Nolan", "Emma Thomas"]
    query = {
        field_name: {
            "$elemMatch": {
                "$type": "string"
            }
        }
    }

    count = await collection.count_documents(query)
    logger.info(f"Found {count} documents to backfill in {collection_name} for field {field_name}")
    
    if count == 0:
        return

    processed = 0
    updated = 0
    
    cursor = collection.find(query)
    async for doc in cursor:
        doc_id = doc["_id"]
        original_data = doc.get(field_name, [])
        
        # Convert legacy string format to the dict format expected by the reconciliation functions
        # The reconciler expects {"tmdb_person_id": int, "name": str, "profile_image": str}
        # But we don't have tmdb_person_id or profile_image, so we pass None
        raw_to_reconcile = []
        for entry in original_data:
            if isinstance(entry, str):
                raw_to_reconcile.append({
                    "tmdb_person_id": None,
                    "name": entry,
                    "profile_image": None
                })
            elif isinstance(entry, dict):
                # Just in case it's partially backfilled
                raw_to_reconcile.append(entry)
                
        reconciled = await reconcile_func(raw_to_reconcile)
        
        await collection.update_one(
            {"_id": doc_id},
            {"$set": {field_name: reconciled}}
        )
        
        processed += 1
        updated += 1
        
        if processed % 50 == 0:
            logger.info(f"Backfill progress ({collection_name}): {processed}/{count}")
            
    logger.info(f"Finished backfilling {collection_name}. Updated {updated} documents.")

async def main():
    await connect_db()
    try:
        await backfill_collection("movies", "director", reconcile_directors)
        await backfill_collection("tv_series", "creators", reconcile_creators)
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
