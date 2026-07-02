"""
Exports existing TV series to CSV for editing, or creates a blank template.

Run:
    python -m app.backend.ingestion.tv_series.export_tv_series_csv

Produces: tv_series_data_template.csv
"""
import asyncio
import csv
import sys

# Ensure Unicode support in Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app.db.mongo import connect_db, close_db, get_db

OUTPUT_FILE = "tv_series_data_template.csv"

FIELDNAMES = [
    "_id",
    "title",
    "year",
    "first_air_date",
    "episode_runtime_minutes",
    "genres",
    "creators",
    "cast",
    "plot",
    "language",
    "country",
    "total_seasons",
    "imdb_rating",
    "imdb_votes",
    "imdb_id",
    "image_poster",
    "status",
]

EXAMPLE_ROWS = [
    {
        "_id": "tv_breaking_bad",
        "title": "Breaking Bad",
        "year": "2008–2013",
        "first_air_date": "20 Jan 2008",
        "episode_runtime_minutes": "49",
        "genres": "Crime;Drama;Thriller",
        "creators": "Vince Gilligan",
        "cast": "Bryan Cranston;Aaron Paul;Anna Gunn",
        "plot": "A chemistry teacher diagnosed with inoperable lung cancer turns to manufacturing and selling methamphetamine with a former student in order to secure his family's future.",
        "language": "English;Spanish",
        "country": "United States",
        "total_seasons": "5",
        "imdb_rating": "9.5",
        "imdb_votes": "2,100,000",
        "imdb_id": "tt0903747",
        "image_poster": "",
        "status": "Ended",
    },
]


def _join(value):
    if not value:
        return ""
    if isinstance(value, list):
        return ";".join(str(v) for v in value)
    return str(value)


def _val(value):
    if value is None:
        return ""
    return value


async def main():
    print("🚀 Exporting TV Series to CSV...")

    await connect_db()
    db = get_db()

    tv_series = await db["tv_series"].find(
        {"is_deleted": {"$ne": True}}
    ).sort("title", 1).to_list(None)

    await close_db()

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        if tv_series:
            for tv in tv_series:
                images = tv.get("images") or {}
                rating = tv.get("rating") or {}
                source = tv.get("source_metadata") or {}

                writer.writerow({
                    "_id": tv["_id"],
                    "title": _val(tv.get("title")),
                    "year": _val(tv.get("year")),
                    "first_air_date": _val(tv.get("first_air_date")),
                    "episode_runtime_minutes": _val(tv.get("episode_runtime_minutes")),
                    "genres": _join(tv.get("genres")),
                    "creators": _join(tv.get("creators")),
                    "cast": _join(tv.get("cast")),
                    "plot": _val(tv.get("plot")),
                    "language": _join(tv.get("language")),
                    "country": _join(tv.get("country")),
                    "total_seasons": _val(tv.get("total_seasons")),
                    "imdb_rating": _val(rating.get("imdb")),
                    "imdb_votes": _val(rating.get("imdb_votes")),
                    "imdb_id": _val(source.get("imdb_id")),
                    "image_poster": _val(images.get("poster")),
                    "status": _val(tv.get("status")),
                })
        else:
            print("📝 No TV Series found — writing example rows as template")
            for row in EXAMPLE_ROWS:
                writer.writerow(row)

    count = len(tv_series) if tv_series else len(EXAMPLE_ROWS)
    print(f"✅ Exported {count} TV Series to {OUTPUT_FILE}")
    print("📝 Fill in data, then run bulk_update_tv_series.py")
    print()
    print("💡 To fetch from OMDb API, run:")
    print("   python -m app.backend.ingestion.tv_series.fetch_tv_series")


if __name__ == "__main__":
    asyncio.run(main())
