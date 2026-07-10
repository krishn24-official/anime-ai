"""
fetch_all.py  -  One-command AniList bulk ingestion
=====================================================
Fetches anime, manga, and characters from AniList using paginated
browse queries (sorted by popularity). No hardcoded title lists needed.

Usage:
    python -m app.backend.ingestion.anime.fetch_all
    python -m app.backend.ingestion.anime.fetch_all --anime-pages 5 --manga-pages 3
    python -m app.backend.ingestion.anime.fetch_all --only anime
    python -m app.backend.ingestion.anime.fetch_all --only characters
"""

import argparse
import asyncio
import sys
import io

# Fix Windows console encoding for emoji / CJK
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import httpx

from app.db.mongo import connect_db, close_db, get_db
from app.backend.transformers.anime_transformer import transform_anime
from app.backend.transformers.manga_transformer import transform_manga
from app.backend.transformers.character_transformer import transform_character
from app.backend.utils.slug import create_slug


ANILIST_URL = "https://graphql.anilist.co"

# AniList rate limit: 90 req/min → ~0.7s between requests
RATE_LIMIT_DELAY = 0.75

# ─────────────────────────────────────────────────
# GraphQL Queries
# ─────────────────────────────────────────────────

ANIME_PAGE_QUERY = """
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
      studios {
        nodes {
          name
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

CHARACTER_PAGE_QUERY = """
query ($mediaId: Int, $page: Int) {
  Media(id: $mediaId, type: ANIME) {
    title {
      english
      romaji
    }
    characters(sort: ROLE, page: $page, perPage: 25) {
      pageInfo {
        hasNextPage
        currentPage
      }
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
      }
    }
  }
}
"""


# ─────────────────────────────────────────────────
# AniList HTTP helper with rate-limit + retry
# ─────────────────────────────────────────────────

async def anilist_request(
    client: httpx.AsyncClient,
    query: str,
    variables: dict,
    max_retries: int = 3,
) -> dict | None:
    """POST to AniList GraphQL with retry + rate-limit handling."""

    for attempt in range(1, max_retries + 1):
        try:
            response = await client.post(
                ANILIST_URL,
                json={"query": query, "variables": variables},
                timeout=30.0,
            )

            # AniList returns 429 when rate-limited
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"    [RATE-LIMITED] Waiting {retry_after}s...")
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
                wait = 2 * attempt
                print(f"    [RETRY {attempt}/{max_retries}] {type(e).__name__}, waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                print(f"    [FAILED] {type(e).__name__} after {max_retries} retries")
                return None

    return None


# ─────────────────────────────────────────────────
# Anime bulk fetch
# ─────────────────────────────────────────────────

async def fetch_all_anime(client: httpx.AsyncClient, max_pages: int = 5):
    db = get_db()
    collection = db["anime"]
    saved = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"  ANIME INGESTION  (up to {max_pages} pages x 50 = {max_pages * 50} anime)")
    print(f"{'='*60}")

    for page in range(1, max_pages + 1):
        data = await anilist_request(client, ANIME_PAGE_QUERY, {"page": page, "perPage": 50})

        if not data:
            print(f"  Page {page}: FAILED to fetch")
            failed += 50
            continue

        page_data = data.get("data", {}).get("Page", {})
        items = page_data.get("media", [])
        page_info = page_data.get("pageInfo", {})

        print(f"\n  Page {page}/{page_info.get('lastPage', '?')}: {len(items)} anime")

        for item in items:
            try:
                doc = transform_anime(item)
                await collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
                saved += 1
                title = doc.get("title", {})
                display = title.get("english") or title.get("romaji") or doc["_id"]
                print(f"    [OK] {doc['_id']} - {display}")
            except Exception as e:
                failed += 1
                print(f"    [ERR] {item.get('title', {}).get('romaji', '?')}: {e}")

        if not page_info.get("hasNextPage", False):
            print("  (No more pages)")
            break

        await asyncio.sleep(RATE_LIMIT_DELAY)

    return {"saved": saved, "failed": failed}


# ─────────────────────────────────────────────────
# Manga bulk fetch
# ─────────────────────────────────────────────────

async def fetch_all_manga(client: httpx.AsyncClient, max_pages: int = 3):
    db = get_db()
    collection = db["manga"]
    saved = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"  MANGA INGESTION  (up to {max_pages} pages x 50 = {max_pages * 50} manga)")
    print(f"{'='*60}")

    for page in range(1, max_pages + 1):
        data = await anilist_request(client, MANGA_PAGE_QUERY, {"page": page, "perPage": 50})

        if not data:
            print(f"  Page {page}: FAILED to fetch")
            failed += 50
            continue

        page_data = data.get("data", {}).get("Page", {})
        items = page_data.get("media", [])
        page_info = page_data.get("pageInfo", {})

        print(f"\n  Page {page}/{page_info.get('lastPage', '?')}: {len(items)} manga")

        for item in items:
            try:
                doc = transform_manga(item)
                await collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
                saved += 1
                display = doc.get("name") or doc["_id"]
                print(f"    [OK] {doc['_id']} - {display}")
            except Exception as e:
                failed += 1
                print(f"    [ERR] {item.get('title', {}).get('romaji', '?')}: {e}")

        if not page_info.get("hasNextPage", False):
            print("  (No more pages)")
            break

        await asyncio.sleep(RATE_LIMIT_DELAY)

    return {"saved": saved, "failed": failed}


# ─────────────────────────────────────────────────
# Characters bulk fetch (from already-ingested anime)
# ─────────────────────────────────────────────────

async def fetch_all_characters(client: httpx.AsyncClient, max_char_pages: int = 4):
    """Fetch characters for every anime already in the database."""
    db = get_db()
    anime_collection = db["anime"]
    char_collection = db["characters"]

    # Get all anime from DB with their AniList IDs
    all_anime = await anime_collection.find(
        {"source_metadata.anilist_id": {"$exists": True}, "is_deleted": {"$ne": True}},
        {"_id": 1, "source_metadata.anilist_id": 1, "title": 1},
    ).to_list(None)

    total_anime = len(all_anime)
    saved = 0
    failed = 0
    skipped = 0

    print(f"\n{'='*60}")
    print(f"  CHARACTER INGESTION  ({total_anime} anime in DB)")
    print(f"  (up to {max_char_pages} character pages per anime)")
    print(f"{'='*60}")

    for idx, anime_doc in enumerate(all_anime, 1):
        anilist_id = anime_doc["source_metadata"]["anilist_id"]
        anime_db_id = anime_doc["_id"]
        title_data = anime_doc.get("title", {})
        display_title = title_data.get("english") or title_data.get("romaji") or anime_db_id

        print(f"\n  [{idx}/{total_anime}] {display_title} (anilist_id={anilist_id})")

        page = 1
        anime_char_count = 0

        while page <= max_char_pages:
            data = await anilist_request(
                client,
                CHARACTER_PAGE_QUERY,
                {"mediaId": anilist_id, "page": page},
            )

            if not data:
                print(f"    Page {page}: FAILED")
                failed += 1
                break

            media = data.get("data", {}).get("Media")
            if not media:
                print(f"    No media returned")
                break

            chars_data = media.get("characters", {})
            edges = chars_data.get("edges", [])

            for edge in edges:
                role = edge.get("role")
                node = edge.get("node")

                if not node or not node.get("name", {}).get("full"):
                    skipped += 1
                    continue

                try:
                    doc = transform_character(node, anime_db_id, role)

                    # Merge anime_ids with existing
                    existing = await char_collection.find_one({"_id": doc["_id"]})
                    if existing:
                        merged = list(set(existing.get("anime_ids", []) + doc["anime_ids"]))
                        doc["anime_ids"] = merged

                    await char_collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
                    saved += 1
                    anime_char_count += 1
                except Exception as e:
                    failed += 1
                    print(f"    [ERR] {node.get('name', {}).get('full', '?')}: {e}")

            has_next = chars_data.get("pageInfo", {}).get("hasNextPage", False)
            if not has_next:
                break

            page += 1
            await asyncio.sleep(RATE_LIMIT_DELAY)

        print(f"    -> {anime_char_count} characters saved")
        await asyncio.sleep(RATE_LIMIT_DELAY)

    return {"saved": saved, "failed": failed, "skipped": skipped}


# ─────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="AniList bulk ingestion")
    parser.add_argument("--anime-pages", type=int, default=5, help="Pages of anime to fetch (50 per page)")
    parser.add_argument("--manga-pages", type=int, default=3, help="Pages of manga to fetch (50 per page)")
    parser.add_argument("--char-pages", type=int, default=4, help="Max character pages per anime (25 per page)")
    parser.add_argument(
        "--only",
        choices=["anime", "manga", "characters", "all"],
        default="all",
        help="Fetch only a specific type",
    )
    args = parser.parse_args()

    print("Connecting to MongoDB...")
    await connect_db()
    print("Connected!\n")

    results = {}

    async with httpx.AsyncClient(verify=False) as client:

        if args.only in ("all", "anime"):
            results["anime"] = await fetch_all_anime(client, max_pages=args.anime_pages)

        if args.only in ("all", "manga"):
            results["manga"] = await fetch_all_manga(client, max_pages=args.manga_pages)

        if args.only in ("all", "characters"):
            results["characters"] = await fetch_all_characters(client, max_char_pages=args.char_pages)

    await close_db()

    # --- Summary ---
    print(f"\n{'='*60}")
    print("  INGESTION COMPLETE")
    print(f"{'='*60}")
    for category, stats in results.items():
        print(f"  {category.upper():>12}: saved={stats['saved']}, failed={stats['failed']}" +
              (f", skipped={stats['skipped']}" if 'skipped' in stats else ""))
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception:
        import traceback
        traceback.print_exc()
