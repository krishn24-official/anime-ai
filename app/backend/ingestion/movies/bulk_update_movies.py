"""
Reads movie_data_template.csv and creates/updates movie documents in MongoDB.
Auto-generates _id (e.g. movie_inception) using the title if the _id field is left blank.

Run:
    python -m app.backend.ingestion.movies.bulk_update_movies
"""
import asyncio
import csv
import re
import sys
import os

from app.db.mongo import connect_db, close_db, get_db
from app.backend.utils.slug import create_slug

# Ensure Unicode support in Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

INPUT_CSV = "movie_data_template.csv"


def _split_list(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    return [v.strip() for v in value.split(";") if v.strip()]


def _parse_int(value: str):
    if not value or not value.strip():
        return None
    try:
        return int(re.sub(r"[^\d]", "", value.strip()))
    except ValueError:
        return None


def _parse_float(value: str):
    if not value or not value.strip():
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def _validate_row(row: dict, row_num: int) -> list[str]:
    warnings = []
    title = row.get("title", "").strip()
    if not title:
        warnings.append(f"Row {row_num}: missing REQUIRED field 'title' — row will be skipped")
    return warnings


def _build_update(row: dict) -> dict:
    update = {}

    # Top-level fields
    if row.get("title", "").strip():
        update["title"] = row["title"].strip()

    if row.get("year", "").strip():
        update["year"] = row["year"].strip()

    if row.get("release_date", "").strip():
        update["release_date"] = row["release_date"].strip()

    runtime = _parse_int(row.get("runtime_minutes", ""))
    if runtime is not None:
        update["runtime_minutes"] = runtime

    genres = _split_list(row.get("genres", ""))
    if genres:
        update["genres"] = genres

    director = _split_list(row.get("director", ""))
    if director:
        update["director"] = director

    writers = _split_list(row.get("writers", ""))
    if writers:
        update["writers"] = writers

    cast = _split_list(row.get("cast", ""))
    if cast:
        update["cast"] = cast

    if row.get("plot", "").strip():
        update["plot"] = row["plot"].strip()

    language = _split_list(row.get("language", ""))
    if language:
        update["language"] = language

    country = _split_list(row.get("country", ""))
    if country:
        update["country"] = country

    if row.get("box_office", "").strip():
        update["box_office"] = row["box_office"].strip()

    # Nested fields
    imdb_rating = _parse_float(row.get("imdb_rating", ""))
    if imdb_rating is not None:
        update["rating.imdb"] = imdb_rating

    if row.get("imdb_votes", "").strip():
        update["rating.imdb_votes"] = row["imdb_votes"].strip()

    if row.get("image_poster", "").strip():
        update["images.poster"] = row["image_poster"].strip()

    if row.get("imdb_id", "").strip():
        update["source_metadata.imdb_id"] = row["imdb_id"].strip()

    return update


async def main():
    print("🚀 Starting bulk movie import...")

    if not os.path.exists(INPUT_CSV):
        print(f"❌ {INPUT_CSV} not found. Run export_movie_csv.py first.")
        return

    try:
        with open(INPUT_CSV, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except Exception as e:
        print(f"❌ Error reading {INPUT_CSV}: {e}")
        return

    # Filter out template example row
    rows = [
        r for r in rows
        if not (
            r.get("_id") == "movie_inception"
            and r.get("title") == "Inception"
            and r.get("plot", "").startswith("A thief who steals")
        )
    ]

    print(f"📊 Read {len(rows)} rows from {INPUT_CSV}\n")

    # Validation pass
    all_warnings = []
    valid_rows = []
    for i, row in enumerate(rows, start=2):
        warnings = _validate_row(row, i)
        if warnings:
            all_warnings.extend(warnings)
            # If title is missing, skip the row entirely
            if not row.get("title", "").strip():
                continue
        valid_rows.append(row)

    if all_warnings:
        print(f"⚠️  {len(all_warnings)} warning(s) / error(s) found:\n")
        for w in all_warnings:
            print(f"  - {w}")
        print()

    if not valid_rows:
        print("❌ No valid rows to import.")
        return

    await connect_db()
    db = get_db()
    col = db["movies"]

    updated = 0

    for row in valid_rows:
        title = row["title"].strip()
        movie_id = row.get("_id", "").strip()

        if not movie_id:
            # Auto generate ID using slug
            movie_id = f"movie_{create_slug(title)}"
            print(f"💡 Auto-generated ID '{movie_id}' for '{title}'")

        update = _build_update(row)

        if not update:
            continue

        await col.update_one(
            {"_id": movie_id},
            {
                "$set": update,
                "$setOnInsert": {
                    "is_deleted": False,
                    "deleted_at": None,
                    "content_type": "movie",
                }
            },
            upsert=True
        )
        updated += 1
        print(f"  ✅ Upserted movie: {movie_id} ({title})")

    await close_db()
    print(f"\n🏁 Done. Movies created/updated: {updated}")


if __name__ == "__main__":
    asyncio.run(main())
