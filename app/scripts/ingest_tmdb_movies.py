import asyncio
import argparse
from datetime import datetime, timezone
import httpx

from app.config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_IMAGE_BASE_URL
from app.db.mongo import connect_db, close_db, get_db
from app.backend.utils.slug import create_slug
from app.backend.ingestion.tmdb_mapper import map_movie
from app.services.cast_reconciliation_service import reconcile_cast, reconcile_directors, reconcile_writers

async def fetch_tmdb_movie(client: httpx.AsyncClient, movie_id: int):
    url = f"{TMDB_BASE_URL}/movie/{movie_id}"
    params = {"api_key": TMDB_API_KEY, "append_to_response": "credits,videos"}
    response = await client.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None

async def process_movie(client: httpx.AsyncClient, movie_id: int, db):
    # 1. Check if movie already exists by tmdb_id
    movies_collection = db["movies"]
    existing_by_tmdb = await movies_collection.find_one({
        "source_metadata.tmdb_id": movie_id, 
        "is_deleted": {"$ne": True}
    })
    
    if existing_by_tmdb:
        print(f"Skipping ID {movie_id}: Already exists by tmdb_id.")
        return

    # 2. Fetch movie details from TMDB
    movie_data = await fetch_tmdb_movie(client, movie_id)
    if not movie_data:
        print(f"Failed to fetch ID {movie_id} from TMDB.")
        return

    title = movie_data.get("title")
    if not title:
        return

    # 3. Check if movie exists by title
    existing_by_title = await movies_collection.find_one({
        "title": title, 
        "is_deleted": {"$ne": True}
    })
    
    if existing_by_title:
        print(f"Skipping {title} (ID {movie_id}): Already exists by title (manual entry).")
        return

    print(f"Ingesting: {title} (ID {movie_id})...")

    # 4. Extract data using map_movie
    doc = map_movie(movie_data)
    
    movie_db_id = doc["_id"]
    base_movie_id = movie_db_id
    counter = 1
    while await movies_collection.find_one({"_id": movie_db_id}):
        movie_db_id = f"{base_movie_id}_{counter}"
        counter += 1
        
    doc["_id"] = movie_db_id
    doc["source_metadata"]["source"] = "tmdb"
    doc["source_metadata"]["created_by"] = "ingestion_script"
    doc["source_metadata"]["created_at"] = datetime.now(timezone.utc)

    # 5. Reconcile Cast & Director
    doc["director"] = await reconcile_directors(doc.get("director", []))
    doc["writer"] = await reconcile_writers(doc.get("writers", []))
    doc["cast"] = await reconcile_cast(doc.get("cast", []))

    await movies_collection.insert_one(doc)
    print(f"Successfully ingested {title}.")

async def ingest_ids(ids: list[int]):
    db = get_db()
    async with httpx.AsyncClient() as client:
        for movie_id in ids:
            try:
                await process_movie(client, movie_id, db)
            except Exception as e:
                print(f"Error processing ID {movie_id}: {e}")

async def ingest_popular(limit: int):
    db = get_db()
    async with httpx.AsyncClient() as client:
        pages = (limit // 20) + (1 if limit % 20 > 0 else 0)
        count = 0
        for page in range(1, pages + 1):
            print(f"Fetching popular movies page {page}...")
            url = f"{TMDB_BASE_URL}/movie/popular"
            params = {"api_key": TMDB_API_KEY, "page": page}
            response = await client.get(url, params=params)
            if response.status_code != 200:
                print(f"Failed to fetch popular page {page}")
                continue
            
            results = response.json().get("results", [])
            for movie in results:
                if count >= limit:
                    return
                movie_id = movie.get("id")
                try:
                    await process_movie(client, movie_id, db)
                    # Respect TMDB rate limit (50 req/sec max)
                    await asyncio.sleep(0.05)
                except Exception as e:
                    print(f"Error processing ID {movie_id}: {e}")
                count += 1

async def main():
    parser = argparse.ArgumentParser(description="Ingest movies from TMDB")
    parser.add_argument("--ids", type=str, help="Comma-separated list of TMDB movie IDs to ingest")
    parser.add_argument("--popular", type=int, help="Number of popular movies to ingest (e.g., 500)")
    
    args = parser.parse_args()
    
    if not args.ids and not args.popular:
        parser.print_help()
        return

    await connect_db()
    
    try:
        if args.ids:
            ids_list = [int(i.strip()) for i in args.ids.split(",") if i.strip().isdigit()]
            print(f"Ingesting specific IDs: {ids_list}")
            await ingest_ids(ids_list)
            
        elif args.popular:
            print(f"Ingesting top {args.popular} popular movies...")
            await ingest_popular(args.popular)
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
