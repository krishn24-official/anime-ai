import asyncio
import os
import gzip
import json
import httpx
import argparse
from datetime import datetime, timedelta, timezone
from io import BytesIO

from app.config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_IMAGE_BASE_URL
from app.db.mongo import connect_db, close_db, get_db
from app.repositories import actors_repository
from app.backend.utils.slug import create_slug

# TMDB daily export URL format: http://files.tmdb.org/p/exports/person_ids_MM_DD_YYYY.json.gz

async def fetch_tmdb_person(client: httpx.AsyncClient, person_id: int):
    url = f"{TMDB_BASE_URL}/person/{person_id}"
    params = {"api_key": TMDB_API_KEY}
    response = await client.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None


async def process_actor(client: httpx.AsyncClient, person_id: int, db):
    # 1. Check if actor already exists by tmdb_id
    existing_by_tmdb = await db["actors"].find_one({"tmdb_id": person_id, "is_deleted": False})
    if existing_by_tmdb:
        print(f"Skipping ID {person_id}: Already exists by tmdb_id.")
        return

    # 2. Fetch person details from TMDB
    person_data = await fetch_tmdb_person(client, person_id)
    if not person_data:
        print(f"Failed to fetch ID {person_id} from TMDB.")
        return

    name = person_data.get("name")
    if not name:
        return

    # 3. Check if actor exists by name
    existing_by_name = await db["actors"].find_one({"name": name, "is_deleted": False})
    if existing_by_name:
        print(f"Skipping {name} (ID {person_id}): Already exists by name (manual entry).")
        return

    print(f"Ingesting: {name} (ID {person_id})...")

    # 4. Handle image
    image_url = None
    profile_path = person_data.get("profile_path")
    if profile_path:
        # Instead of downloading and uploading, just store the TMDB URL
        image_url = f"{TMDB_IMAGE_BASE_URL}/original{profile_path}"
    
    slug = create_slug(name)
    # Append uuid to make it unique if slug exists
    base_actor_id = f"actor_{slug}"
    actor_id = base_actor_id
    counter = 1
    while await db["actors"].find_one({"_id": actor_id}):
        actor_id = f"{base_actor_id}_{counter}"
        counter += 1

    # 5. Save to DB
    doc = {
        "_id": actor_id,
        "tmdb_id": person_id,
        "name": name,
        "birthdate": person_data.get("birthday"),
        "biography": person_data.get("biography"),
        "images": {
            "profile": image_url
        },
        "is_deleted": False,
        "deleted_at": None,
        "source_metadata": {
            "source": "tmdb",
            "created_by": "ingestion_script",
            "created_at": datetime.now(timezone.utc)
        }
    }

    await actors_repository.create_actor(doc)
    print(f"Successfully ingested {name}.")

async def get_daily_export_url():
    # TMDB exports are usually generated for the previous day early in the morning
    # Try today first, if 404, try yesterday
    async with httpx.AsyncClient() as client:
        today = datetime.now()
        date_str = today.strftime("%m_%d_%Y")
        url = f"http://files.tmdb.org/p/exports/person_ids_{date_str}.json.gz"
        resp = await client.head(url)
        if resp.status_code == 200:
            return url
            
        yesterday = today - timedelta(days=1)
        date_str = yesterday.strftime("%m_%d_%Y")
        url = f"http://files.tmdb.org/p/exports/person_ids_{date_str}.json.gz"
        return url

async def ingest_all():
    url = await get_daily_export_url()
    print(f"Downloading daily export from {url}...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url)
        if response.status_code != 200:
            print("Failed to download daily export.")
            return

        db = get_db()
        print("Extracting IDs...")
        with gzip.GzipFile(fileobj=BytesIO(response.content)) as f:
            lines = f.readlines()
        
        print(f"Found {len(lines)} persons in the export.")
        
        for line in lines:
            data = json.loads(line)
            person_id = data.get("id")
            if person_id:
                try:
                    await process_actor(client, person_id, db)
                    # Respect TMDB rate limit (50 req/sec max)
                    await asyncio.sleep(0.05)
                except Exception as e:
                    print(f"Error processing ID {person_id}: {e}")

async def ingest_ids(ids: list[int]):
    db = get_db()
    async with httpx.AsyncClient() as client:
        for person_id in ids:
            try:
                await process_actor(client, person_id, db)
            except Exception as e:
                print(f"Error processing ID {person_id}: {e}")

async def ingest_popular(limit: int):
    db = get_db()
    async with httpx.AsyncClient() as client:
        pages = (limit // 20) + (1 if limit % 20 > 0 else 0)
        count = 0
        for page in range(1, pages + 1):
            print(f"Fetching popular actors page {page}...")
            url = f"{TMDB_BASE_URL}/person/popular"
            params = {"api_key": TMDB_API_KEY, "page": page}
            response = await client.get(url, params=params)
            if response.status_code != 200:
                print(f"Failed to fetch popular page {page}")
                continue
            
            results = response.json().get("results", [])
            for person in results:
                if count >= limit:
                    return
                person_id = person.get("id")
                try:
                    await process_actor(client, person_id, db)
                    # Respect TMDB rate limit (50 req/sec max)
                    await asyncio.sleep(0.05)
                except Exception as e:
                    print(f"Error processing ID {person_id}: {e}")
                count += 1

async def main():
    parser = argparse.ArgumentParser(description="Ingest actors from TMDB")
    parser.add_argument("--all", action="store_true", help="Download and ingest all actors from daily export")
    parser.add_argument("--ids", type=str, help="Comma-separated list of TMDB person IDs to ingest")
    parser.add_argument("--popular", type=int, help="Number of popular actors to ingest (e.g., 500)")
    
    args = parser.parse_args()
    
    if not args.all and not args.ids and not args.popular:
        parser.print_help()
        return

    await connect_db()
    
    try:
        if args.ids:
            ids_list = [int(i.strip()) for i in args.ids.split(",") if i.strip().isdigit()]
            print(f"Ingesting specific IDs: {ids_list}")
            await ingest_ids(ids_list)
            
        elif args.popular:
            print(f"Ingesting top {args.popular} popular actors...")
            await ingest_popular(args.popular)
            
        elif args.all:
            print("WARNING: Ingesting all actors from daily export can take a very long time!")
            await ingest_all()
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
