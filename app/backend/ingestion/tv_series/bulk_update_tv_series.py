"""
Reads tv_series_data_template.csv and creates/updates TV series documents in MongoDB.
Auto-generates _id (e.g. tv_breaking_bad) using the title if the _id field is left blank.

Run:
    python -m app.backend.ingestion.tv_series.bulk_update_tv_series
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

INPUT_CSV = "tv_series_data_template.csv"


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

    if row.get("first_air_date", "").strip():
        update["first_air_date"] = row["first_air_date"].strip()

    episode_runtime = _parse_int(row.get("episode_runtime_minutes", ""))
    if episode_runtime is not None:
        update["episode_runtime_minutes"] = episode_runtime

    genres = _split_list(row.get("genres", ""))
    if genres:
        update["genres"] = genres

    creators = _split_list(row.get("creators", ""))
    if creators:
        update["creators"] = creators

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

    total_seasons = _parse_int(row.get("total_seasons", ""))
    if total_seasons is not None:
        update["total_seasons"] = total_seasons

    if row.get("status", "").strip():
        update["status"] = row["status"].strip()

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
    print("🚀 Starting bulk TV series import...")

    if not os.path.exists(INPUT_CSV):
        print(f"❌ {INPUT_CSV} not found. Run export_tv_series_csv.py first.")
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
            r.get("_id") == "tv_breaking_bad"
            and r.get("title") == "Breaking Bad"
            and r.get("plot", "").startswith("A chemistry teacher")
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
    col = db["tv_series"]

    updated = 0

    for row in valid_rows:
        title = row["title"].strip()
        tv_id = row.get("_id", "").strip()

        if not tv_id:
            # Auto generate ID using slug
            tv_id = f"tv_{create_slug(title)}"
            print(f"💡 Auto-generated ID '{tv_id}' for '{title}'")

        update = _build_update(row)

        if not update:
            continue

        await col.update_one(
            {"_id": tv_id},
            {
                "$set": update,
                "$setOnInsert": {
                    "is_deleted": False,
                    "deleted_at": None,
                    "content_type": "tv_series",
                }
            },
            upsert=True
        )
        updated += 1
        print(f"  ✅ Upserted TV series: {tv_id} ({title})")

    await close_db()
    print(f"\n🏁 Done. TV series created/updated: {updated}")


if __name__ == "__main__":
    asyncio.run(main())
