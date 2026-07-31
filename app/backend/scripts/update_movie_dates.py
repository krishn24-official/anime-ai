import asyncio
import sys
import io

# Fix Windows console encoding for emoji
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db, get_db
from app.backend.ingestion.tmdb_client import get_movie_details, close_client
from app.backend.ingestion.tmdb_mapper import _extract_us_theatrical_release_date

async def main():
    print("Connecting to MongoDB...")
    await connect_db()
    
    db = get_db()
    movies_cursor = db["movies"].find({"is_deleted": {"$ne": True}})
    movies = await movies_cursor.to_list(None)
    
    print(f"Found {len(movies)} movies to process.")
    
    updated_count = 0
    failed_count = 0
    
    for i, movie in enumerate(movies):
        tmdb_id = movie.get("source_metadata", {}).get("tmdb_id")
        
        if not tmdb_id:
            print(f"[{i+1}/{len(movies)}] Skipping {movie.get('title')} (No TMDB ID)")
            continue
            
        try:
            details = await get_movie_details(tmdb_id)
            if not details:
                print(f"[{i+1}/{len(movies)}] Failed to fetch TMDB details for {movie.get('title')}")
                failed_count += 1
                continue
                
            actual_release_date = _extract_us_theatrical_release_date(details)
            year = (actual_release_date or "")[:4] or None
            
            old_date = movie.get("release_date")
            if actual_release_date != old_date:
                print(f"[{i+1}/{len(movies)}] Updating {movie.get('title')}: {old_date} -> {actual_release_date}")
                await db["movies"].update_one(
                    {"_id": movie["_id"]},
                    {"$set": {
                        "release_date": actual_release_date,
                        "year": year
                    }}
                )
                updated_count += 1
            else:
                print(f"[{i+1}/{len(movies)}] No change for {movie.get('title')} ({actual_release_date})")
                
        except Exception as e:
            print(f"[{i+1}/{len(movies)}] Error processing {movie.get('title')}: {e}")
            failed_count += 1
            
        # Sleep slightly to avoid hitting rate limits too hard
        await asyncio.sleep(0.1)
        
    print(f"\nDone. Updated {updated_count} movies. Failed {failed_count}.")
    
    await close_client()
    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
