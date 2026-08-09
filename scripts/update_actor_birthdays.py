import sys
import io
import asyncio
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Fix Windows console encoding for emoji / CJK
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db, get_db
from app.backend.ingestion.tmdb_client import get_person_details, close_client

async def main():
    print("Connecting to MongoDB...")
    await connect_db()
    db = get_db()
    
    # Find all actors who have a tmdb_id but no birthdate
    query = {
        "is_deleted": False,
        "tmdb_id": {"$ne": None},
        "$or": [
            {"birthdate": None},
            {"birthdate": ""}
        ]
    }
    
    cursor = db["actors"].find(query)
    actors = await cursor.to_list(None)
    
    print(f"Found {len(actors)} actors with missing birthdate.")
    
    updated_count = 0
    for i, actor in enumerate(actors):
        actor_id = actor["_id"]
        tmdb_id = actor["tmdb_id"]
        name = actor.get("name", "Unknown")
        
        print(f"[{i+1}/{len(actors)}] Fetching for {name} (TMDB: {tmdb_id})...")
        
        details = await get_person_details(tmdb_id)
        if details:
            birthday = details.get("birthday")
            if birthday:
                # Update in DB
                await db["actors"].update_one(
                    {"_id": actor_id},
                    {"$set": {"birthdate": birthday}}
                )
                updated_count += 1
                print(f"  -> Updated {name} with birthday {birthday}")
            else:
                print(f"  -> No birthday found on TMDB for {name}")
        else:
            print(f"  -> Failed to fetch details for {name}")
            
        await asyncio.sleep(0.1)
        
    print(f"\nFinished updating {updated_count} actors.")
    
    await close_client()
    await close_db()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
