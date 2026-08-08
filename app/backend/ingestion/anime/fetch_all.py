"""
fetch_all.py  -  One-command AniList bulk ingestion
=====================================================
Fetches anime, manga, and characters from AniList using paginated
browse queries (sorted by popularity) and batched character/staff data.

Usage:
    python -m app.backend.ingestion.anime.fetch_all --only all
    python -m app.backend.ingestion.anime.fetch_all --only anime --top 10000
    python -m app.backend.ingestion.anime.fetch_all --backfill
"""

import argparse
import asyncio
import sys
import io
import time
from datetime import datetime, timezone
import httpx

# Fix Windows console encoding for emoji / CJK
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db, get_db
from app.backend.transformers.anime_transformer import transform_anime
from app.backend.transformers.manga_transformer import transform_manga
from app.backend.ingestion.anime.anilist_resolvers import (
    resolve_or_create_voice_actor,
    resolve_or_create_character,
)
from app.backend.utils.slug import create_slug

ANILIST_URL = "https://graphql.anilist.co"

# ─────────────────────────────────────────────────
# GraphQL Queries
# ─────────────────────────────────────────────────

ANIME_UNIFIED_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      total
      currentPage
      lastPage
      hasNextPage
    }
    media(type: ANIME, sort: POPULARITY_DESC) {
      id
      title {
        english
        romaji
        native
      }
      synonyms
      format
      status
      genres
      season
      seasonYear
      source
      episodes
      duration
      averageScore
      coverImage {
        large
      }
      bannerImage
      startDate {
        year
        month
        day
      }
      endDate {
        year
        month
        day
      }
      studios {
        nodes {
          name
        }
      }
      characters(sort: ROLE, perPage: 25) {
        edges {
          role
          node {
            id
            name {
              full
              native
            }
            image {
              large
            }
            gender
            description
            age
            dateOfBirth {
              day
              month
            }
          }
          voiceActors(language: JAPANESE) {
            id
            name {
              full
              native
            }
            image {
              large
            }
            description
            gender
            dateOfBirth {
              year
              month
              day
            }
          }
        }
      }
    }
  }
}
"""

MANGA_PAGE_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      total
      currentPage
      lastPage
      hasNextPage
    }
    media(type: MANGA, sort: POPULARITY_DESC) {
      id
      title {
        romaji
        english
        native
      }
      description
      chapters
      volumes
      status
      genres
      bannerImage
      coverImage {
        large
      }
      startDate {
        year
        month
        day
      }
      endDate {
        year
        month
        day
      }
      staff {
        edges {
          role
          node {
            name {
              full
            }
          }
        }
      }
    }
  }
}
"""

BACKFILL_ANIME_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    startDate {
      year
      month
      day
    }
    endDate {
      year
      month
      day
    }
    characters(sort: ROLE, perPage: 25) {
      edges {
        role
        node {
          id
          name {
            full
            native
          }
          image {
            large
          }
          gender
          description
          age
          dateOfBirth {
            day
            month
          }
        }
        voiceActors(language: JAPANESE) {
          id
          name {
            full
            native
          }
          image {
            large
          }
          description
          gender
          dateOfBirth {
            year
            month
            day
          }
        }
      }
    }
  }
}
"""


# ─────────────────────────────────────────────────
# Utils
# ─────────────────────────────────────────────────

class AniListRateLimiter:
    def __init__(self, limit=90, window=60):
        self.limit = limit
        self.window = window
        self.timestamps = []

    async def wait_if_needed(self):
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < self.window]
        
        if len(self.timestamps) >= self.limit - 2:
            wait_time = self.window - (now - self.timestamps[0])
            if wait_time > 0:
                print(f"    [RATE LIMITER] Proactive pause for {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
            
            now = time.time()
            self.timestamps = [t for t in self.timestamps if now - t < self.window]
            
        self.timestamps.append(time.time())

class CheckpointManager:
    def __init__(self, mode: str):
        self.mode = mode
        self.collection = get_db()["anilist_sync_state"]
        
    async def get_last_page(self) -> int:
        doc = await self.collection.find_one({"_id": self.mode})
        if doc:
            return doc.get("last_completed_page", 0)
        return 0
        
    async def save_progress(self, page: int):
        await self.collection.update_one(
            {"_id": self.mode},
            {"$set": {"last_completed_page": page, "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )

async def anilist_request(
    client: httpx.AsyncClient,
    limiter: AniListRateLimiter,
    query: str,
    variables: dict,
    max_retries: int = 4,
) -> dict | None:
    for attempt in range(1, max_retries + 1):
        await limiter.wait_if_needed()
        try:
            response = await client.post(
                ANILIST_URL,
                json={"query": query, "variables": variables},
                timeout=30.0,
            )

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"    [429 RATE-LIMITED] Waiting {retry_after}s...")
                await asyncio.sleep(retry_after)
                continue

            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                print(f"    [GQL ERROR] {data['errors']}")
                return None

            return data

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            if attempt < max_retries:
                wait = (2 ** attempt)
                print(f"    [RETRY {attempt}/{max_retries}] {type(e).__name__}, waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                print(f"    [FAILED] {type(e).__name__} after {max_retries} retries")
                return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500 and attempt < max_retries:
                wait = (2 ** attempt)
                print(f"    [SERVER ERROR {e.response.status_code}] waiting {wait}s...")
                await asyncio.sleep(wait)
                continue
            else:
                print(f"    [HTTP ERROR] {e}")
                return None

    return None


# ─────────────────────────────────────────────────
# Processors
# ─────────────────────────────────────────────────

async def process_anime_node(item: dict) -> bool:
    db = get_db()
    try:
        doc = transform_anime(item)
        anime_id = doc["_id"]

        # Process characters and voice actors
        characters_data = item.get("characters", {}).get("edges", [])
        for edge in characters_data:
            role = edge.get("role")
            char_node = edge.get("node")

            if not char_node or not char_node.get("name", {}).get("full"):
                continue

            try:
                # ── Resolve voice actor (id-based dedup) ───────────────────────────────
                va_ids = []
                voice_actors = edge.get("voiceActors", [])
                if voice_actors:
                    va_id = await resolve_or_create_voice_actor(voice_actors[0])
                    if va_id:
                        va_ids = [va_id]

                # ── Resolve character (anilist_id-based dedup) ───────────────────────
                # Primary key: source_metadata.anilist_id  — prevents name collisions.
                # Two characters with the same display name but different anilist ids
                # will be stored as separate documents (e.g. two different ‘Kohaku’s).
                await resolve_or_create_character(
                    char_node=char_node,
                    anime_id=anime_id,
                    role=role,
                    voice_actor_ids=va_ids,
                )
            except Exception as e:
                print(f"    [ERR CHAR] {char_node.get('name', {}).get('full', '?')}: {e}")

        await db["anime"].replace_one({"_id": anime_id}, doc, upsert=True)
        return True
    except Exception as e:
        print(f"    [ERR ANIME] {item.get('title', {}).get('romaji', '?')}: {e}")
        return False

async def fetch_anime_unified(client: httpx.AsyncClient, limiter: AniListRateLimiter, top: int = None):
    db = get_db()
    checkpoint = CheckpointManager("anime_all")
    start_page = await checkpoint.get_last_page() + 1
    
    saved = 0
    failed = 0
    max_items = top or float('inf')

    print(f"\n{'='*60}")
    print(f"  ANIME + CHARACTERS INGESTION")
    print(f"  Resuming from page: {start_page}")
    print(f"{'='*60}")

    page = start_page
    while True:
        if saved + failed >= max_items:
            print(f"  Reached target limit of {max_items}. Stopping.")
            break

        data = await anilist_request(client, limiter, ANIME_UNIFIED_QUERY, {"page": page, "perPage": 50})

        if not data:
            print(f"  Page {page}: FAILED to fetch")
            failed += 50
            break

        page_data = data.get("data", {}).get("Page", {})
        items = page_data.get("media", [])
        page_info = page_data.get("pageInfo", {})

        print(f"\n  Page {page}/{page_info.get('lastPage', '?')}: {len(items)} anime")

        for item in items:
            if saved + failed >= max_items:
                break
                
            success = await process_anime_node(item)
            if success:
                saved += 1
                title = item.get("title", {})
                display = title.get("english") or title.get("romaji")
                print(f"    [OK] {display}")
            else:
                failed += 1
                
        await checkpoint.save_progress(page)
        
        if not page_info.get("hasNextPage", False):
            print("  (No more pages)")
            break
            
        page += 1

    return {"saved": saved, "failed": failed}

async def fetch_all_manga(client: httpx.AsyncClient, limiter: AniListRateLimiter, top: int = None):
    db = get_db()
    collection = db["manga"]
    checkpoint = CheckpointManager("manga_all")
    start_page = await checkpoint.get_last_page() + 1
    
    saved = 0
    failed = 0
    max_items = top or float('inf')

    print(f"\n{'='*60}")
    print(f"  MANGA INGESTION")
    print(f"  Resuming from page: {start_page}")
    print(f"{'='*60}")

    page = start_page
    while True:
        if saved + failed >= max_items:
            print(f"  Reached target limit of {max_items}. Stopping.")
            break
            
        data = await anilist_request(client, limiter, MANGA_PAGE_QUERY, {"page": page, "perPage": 50})

        if not data:
            print(f"  Page {page}: FAILED to fetch")
            failed += 50
            break

        page_data = data.get("data", {}).get("Page", {})
        items = page_data.get("media", [])
        page_info = page_data.get("pageInfo", {})

        print(f"\n  Page {page}/{page_info.get('lastPage', '?')}: {len(items)} manga")

        for item in items:
            if saved + failed >= max_items:
                break
            try:
                doc = transform_manga(item)
                await collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
                saved += 1
                display = doc.get("name") or doc["_id"]
                print(f"    [OK] {doc['_id']} - {display}")
            except Exception as e:
                failed += 1
                print(f"    [ERR] {item.get('title', {}).get('romaji', '?')}: {e}")
                
        await checkpoint.save_progress(page)

        if not page_info.get("hasNextPage", False):
            print("  (No more pages)")
            break
            
        page += 1

    return {"saved": saved, "failed": failed}

async def run_backfill(client: httpx.AsyncClient, limiter: AniListRateLimiter):
    db = get_db()
    anime_collection = db["anime"]

    all_anime = await anime_collection.find(
        {"source_metadata.anilist_id": {"$exists": True}, "is_deleted": {"$ne": True}},
        {"_id": 1, "source_metadata.anilist_id": 1, "title": 1},
    ).to_list(None)

    total_anime = len(all_anime)
    saved = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"  BACKFILL ANIME ({total_anime} items in DB)")
    print(f"{'='*60}")

    for idx, anime_doc in enumerate(all_anime, 1):
        anilist_id = anime_doc["source_metadata"]["anilist_id"]
        title_data = anime_doc.get("title", {})
        display_title = title_data.get("english") or title_data.get("romaji") or anime_doc["_id"]

        print(f"\n  [{idx}/{total_anime}] {display_title} (anilist_id={anilist_id})")

        data = await anilist_request(client, limiter, BACKFILL_ANIME_QUERY, {"id": anilist_id})
        if not data:
            failed += 1
            continue

        media = data.get("data", {}).get("Media")
        if not media:
            failed += 1
            continue
            
        success = await process_anime_node(media)
        if success:
            saved += 1
        else:
            failed += 1

    return {"saved": saved, "failed": failed}


# ─────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="AniList bulk ingestion")
    parser.add_argument(
        "--only",
        choices=["anime", "manga", "all"],
        default="all",
        help="Fetch only a specific type",
    )
    parser.add_argument("--top", type=int, default=None, help="Cap fetching at top N items (e.g. 10000)")
    parser.add_argument("--backfill", action="store_true", help="Backfill voice actors and release dates for existing anime")
    args = parser.parse_args()

    print("Connecting to MongoDB...")
    await connect_db()
    print("Connected!\n")

    results = {}
    limiter = AniListRateLimiter()

    async with httpx.AsyncClient(verify=False) as client:
        if args.backfill:
            results["backfill"] = await run_backfill(client, limiter)
        else:
            if args.only in ("all", "anime"):
                results["anime"] = await fetch_anime_unified(client, limiter, top=args.top)

            if args.only in ("all", "manga"):
                results["manga"] = await fetch_all_manga(client, limiter, top=args.top)

    await close_db()

    # --- Summary ---
    print(f"\n{'='*60}")
    print("  INGESTION COMPLETE")
    print(f"{'='*60}")
    for category, stats in results.items():
        print(f"  {category.upper():>12}: saved={stats['saved']}, failed={stats['failed']}")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user. Progress was saved in checkpoint.")
    except Exception:
        import traceback
        traceback.print_exc()
