import asyncio
import argparse
import sys
import io

# Fix Windows console encoding for emoji / CJK
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from app.db.mongo import connect_db, close_db, get_db
from app.backend.ingestion.tmdb_client import get_movie_details, get_person_details, get_tv_details

async def process_movie(db, movie, sem):
    tmdb_id = movie.get("source_metadata", {}).get("tmdb_id")
    if not tmdb_id:
        return
    
    async with sem:
        details = await get_movie_details(tmdb_id)
        
    if details and details.get("adult") is True:
        print(f"Deleting Adult Movie: {movie.get('title')} (TMDB: {tmdb_id})")
        await db["movies"].delete_one({"_id": movie["_id"]})
        # Clean up related records
        await db["relationships"].delete_many({"$or": [{"source_id": movie["_id"]}, {"target_id": movie["_id"]}]})
        await db["events"].delete_many({"$or": [{"content_id": movie["_id"]}, {"movie_id": movie["_id"]}]})

async def process_tv_series(db, tv, sem):
    tmdb_id = tv.get("source_metadata", {}).get("tmdb_id")
    if not tmdb_id:
        return
    
    async with sem:
        details = await get_tv_details(tmdb_id)
        
    if details and details.get("adult") is True:
        print(f"Deleting Adult TV Series: {tv.get('title')} (TMDB: {tmdb_id})")
        tv_id = tv["_id"]
        await db["tv_series"].delete_one({"_id": tv_id})
        # Clean up related episodes and references
        await db["episodes"].delete_many({"$or": [{"parent_id": tv_id}, {"tv_series_id": tv_id}]})
        await db["relationships"].delete_many({"$or": [{"source_id": tv_id}, {"target_id": tv_id}]})
        await db["events"].delete_many({"$or": [{"content_id": tv_id}, {"tv_id": tv_id}, {"tv_series_id": tv_id}]})

async def process_actor(db, actor, sem):
    tmdb_id = actor.get("tmdb_id")
    if not tmdb_id:
        return
    
    async with sem:
        details = await get_person_details(tmdb_id)
        
    if details and details.get("adult") is True:
        print(f"Deleting Adult Actor: {actor.get('name')} (TMDB: {tmdb_id})")
        await db["actors"].delete_one({"_id": actor["_id"]})

async def main():
    parser = argparse.ArgumentParser(description="Remove adult movies, TV series, and actors from DB")
    parser.add_argument("--movies", action="store_true", help="Clean up adult movies")
    parser.add_argument("--tv", action="store_true", help="Clean up adult TV series")
    parser.add_argument("--actors", action="store_true", help="Clean up adult actors")
    args = parser.parse_args()

    if not args.movies and not args.tv and not args.actors:
        print("Please specify --movies, --tv, --actors, or any combination.")
        return

    await connect_db()
    db = get_db()
    sem = asyncio.Semaphore(15) # concurrent requests to respect rate limit

    try:
        if args.movies:
            print("Fetching all TMDB movies from DB...")
            movies_cursor = db["movies"].find({"source_metadata.tmdb_id": {"$exists": True}})
            movies = await movies_cursor.to_list(length=None)
            print(f"Found {len(movies)} TMDB movies. Checking for adult content...")
            
            tasks = [process_movie(db, m, sem) for m in movies]
            await asyncio.gather(*tasks)

        if args.tv:
            print("Fetching all TMDB TV series from DB...")
            tv_cursor = db["tv_series"].find({"source_metadata.tmdb_id": {"$exists": True}})
            tv_list = await tv_cursor.to_list(length=None)
            print(f"Found {len(tv_list)} TMDB TV series. Checking for adult content...")
            
            tasks = [process_tv_series(db, tv, sem) for tv in tv_list]
            await asyncio.gather(*tasks)

        if args.actors:
            print("Fetching all TMDB actors from DB...")
            actors_cursor = db["actors"].find({"tmdb_id": {"$exists": True}})
            actors = await actors_cursor.to_list(length=None)
            print(f"Found {len(actors)} TMDB actors. Checking for adult content...")
            
            tasks = [process_actor(db, a, sem) for a in actors]
            await asyncio.gather(*tasks)
            
        print("Cleanup complete!")
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
