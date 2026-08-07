import asyncio
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db, get_db

async def main():
    print("Starting duplicate flags mirroring...")
    await connect_db()
    db = get_db()
    
    collections = ["anime", "movies", "tv_series"]
    
    count = 0
    for coll in collections:
        print(f"Scanning {coll} for existing flags...")
        cursor = db[coll].find({"possible_duplicate_of": {"$exists": True, "$ne": None}})
        
        async for doc in cursor:
            dup = doc["possible_duplicate_of"]
            target_coll = dup["content_type"]
            target_id = dup["content_id"]
            
            # Map content types to collection names if needed
            if target_coll == "tv_series":
                target_coll_name = "tv_series"
            elif target_coll == "movie":
                target_coll_name = "movies"
            elif target_coll == "anime":
                target_coll_name = "anime"
            else:
                continue
                
            # Update the target document to point back to this one
            reciprocal_dup = {
                "content_type": coll if coll != "movies" else "movie",
                "content_id": doc["_id"]
            }
            
            await db[target_coll_name].update_one(
                {"_id": target_id},
                {"$set": {"possible_duplicate_of": reciprocal_dup}}
            )
            count += 1
            
    print(f"Mirrored {count} duplicate flags across collections.")
    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
