import argparse
import asyncio
import sys
import io

# Fix Windows console encoding for emoji / CJK
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db, get_db
from app.backend.ingestion.tmdb_client import (
    close_client,
    search_person,
    get_person_movie_credits,
    get_movie_details,
)
from app.backend.ingestion.tmdb_mapper import map_movie
from app.repositories.movie_repository import upsert_movie
from app.services.cast_reconciliation_service import reconcile_cast, reconcile_directors, reconcile_writers


async def main():
    parser = argparse.ArgumentParser(description="Fetch movies for a specific actor from TMDb")
    parser.add_argument("--actor", type=str, help="Name of the actor to search for")
    parser.add_argument("--actor-id", type=int, help="TMDb ID of the actor")
    parser.add_argument("--max-cast", type=int, default=10, help="Maximum number of cast members to fetch per movie")
    args = parser.parse_args()

    if not args.actor and not args.actor_id:
        print("Please provide either --actor (name) or --actor-id (TMDb ID).")
        return

    print("Connecting to MongoDB...")
    await connect_db()
    
    try:
        actor_tmdb_id = args.actor_id
        actor_name = args.actor

        if not actor_tmdb_id and actor_name:
            print(f"Searching for actor: '{actor_name}'...")
            results = await search_person(actor_name)
            if not results:
                print(f"Actor '{actor_name}' not found on TMDb.")
                return
            
            # Use the most popular match
            person = results[0]
            actor_tmdb_id = person["id"]
            actor_name = person["name"]
            print(f"Found actor: {actor_name} (TMDb ID: {actor_tmdb_id})")

        print(f"Fetching movie credits for actor ID: {actor_tmdb_id}...")
        credits = await get_person_movie_credits(actor_tmdb_id)
        print(f"Found {len(credits)} movies in their credits.\n")

        db = get_db()
        movies_collection = db["movies"]

        saved = 0
        skipped = 0
        failed = 0

        for idx, credit in enumerate(credits, start=1):
            tmdb_id = credit["id"]
            title = credit.get("title") or credit.get("original_title") or "Unknown"

            # Check if movie already exists using TMDB ID
            existing = await movies_collection.find_one({"tmdb_id": tmdb_id})
            if existing:
                print(f"  [{idx}/{len(credits)}] ⏭️ Skipped (already exists): {title} ({existing['_id']})")
                skipped += 1
                continue

            print(f"  [{idx}/{len(credits)}] ⬇️ Fetching: {title} (TMDB: {tmdb_id})")
            details = await get_movie_details(tmdb_id)

            if not details:
                failed += 1
                print(f"    [FAIL] Could not fetch details for tmdb_id={tmdb_id}")
                continue

            doc = map_movie(details, max_cast=args.max_cast)
            
            # Map returns base doc. Let's resolve actors for cast & crew
            doc["director"] = await reconcile_directors(doc.get("director", []))
            doc["writer"] = await reconcile_writers(doc.get("writers", []))
            doc["cast"] = await reconcile_cast(doc.get("cast", []))
            
            # Save the movie
            await upsert_movie(doc)
            saved += 1
            print(f"    [OK] Saved: {doc['_id']}")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await close_client()
        await close_db()
        
    print(f"\n============================================================")
    print("  TMDb ACTOR MOVIES INGESTION COMPLETE")
    print(f"============================================================")
    print(f"  Saved new movies : {saved}")
    print(f"  Skipped existing : {skipped}")
    print(f"  Failed to fetch  : {failed}")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
