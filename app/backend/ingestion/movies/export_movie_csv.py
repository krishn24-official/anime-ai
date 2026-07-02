"""
Exports existing movies to CSV for editing, or creates a blank template.

Run:
    python -m app.backend.ingestion.movies.export_movie_csv

Produces: movie_data_template.csv

CSV columns:
  _id           -- e.g. "movie_inception" (auto-generated from title if blank)
  title         -- REQUIRED
  year          -- e.g. "2010"
  release_date  -- e.g. "16 Jul 2010"
  runtime_minutes -- e.g. "148"
  genres        -- semicolon-separated, e.g. "Action;Sci-Fi;Thriller"
  director      -- semicolon-separated
  writers       -- semicolon-separated
  cast          -- semicolon-separated (top actors)
  plot          -- full plot description
  language      -- semicolon-separated, e.g. "English"
  country       -- semicolon-separated
  box_office    -- e.g. "$836,836,967"
  imdb_rating   -- e.g. "8.8"
  imdb_votes    -- e.g. "2,400,000"
  imdb_id       -- e.g. "tt1375666"
  image_poster  -- poster image URL (Cloudinary or external)

Leave a cell EMPTY to skip updating that field.
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

OUTPUT_FILE = "movie_data_template.csv"

FIELDNAMES = [
    "_id",
    "title",
    "year",
    "release_date",
    "runtime_minutes",
    "genres",
    "director",
    "writers",
    "cast",
    "plot",
    "language",
    "country",
    "box_office",
    "imdb_rating",
    "imdb_votes",
    "imdb_id",
    "image_poster",
]

EXAMPLE_ROWS = [
    {
        "_id": "movie_inception",
        "title": "Inception",
        "year": "2010",
        "release_date": "16 Jul 2010",
        "runtime_minutes": "148",
        "genres": "Action;Adventure;Sci-Fi",
        "director": "Christopher Nolan",
        "writers": "Christopher Nolan",
        "cast": "Leonardo DiCaprio;Joseph Gordon-Levitt;Elliot Page",
        "plot": "A thief who steals corporate secrets through the use of dream-sharing technology...",
        "language": "English;Japanese;French",
        "country": "United States;United Kingdom",
        "box_office": "$292,576,195",
        "imdb_rating": "8.8",
        "imdb_votes": "2,400,000",
        "imdb_id": "tt1375666",
        "image_poster": "",
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
    print("🚀 Exporting movies to CSV...")

    await connect_db()
    db = get_db()

    movies = await db["movies"].find(
        {"is_deleted": {"$ne": True}}
    ).sort("title", 1).to_list(None)

    await close_db()

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        if movies:
            for movie in movies:
                images = movie.get("images") or {}
                rating = movie.get("rating") or {}
                source = movie.get("source_metadata") or {}

                writer.writerow({
                    "_id": movie["_id"],
                    "title": _val(movie.get("title")),
                    "year": _val(movie.get("year")),
                    "release_date": _val(movie.get("release_date")),
                    "runtime_minutes": _val(movie.get("runtime_minutes")),
                    "genres": _join(movie.get("genres")),
                    "director": _join(movie.get("director")),
                    "writers": _join(movie.get("writers")),
                    "cast": _join(movie.get("cast")),
                    "plot": _val(movie.get("plot")),
                    "language": _join(movie.get("language")),
                    "country": _join(movie.get("country")),
                    "box_office": _val(movie.get("box_office")),
                    "imdb_rating": _val(rating.get("imdb")),
                    "imdb_votes": _val(rating.get("imdb_votes")),
                    "imdb_id": _val(source.get("imdb_id")),
                    "image_poster": _val(images.get("poster")),
                })
        else:
            print("📝 No movies found — writing example rows as template")
            for row in EXAMPLE_ROWS:
                writer.writerow(row)

    count = len(movies) if movies else len(EXAMPLE_ROWS)
    print(f"✅ Exported {count} movies to {OUTPUT_FILE}")
    print("📝 Fill in data, then run bulk_update_movies.py")
    print()
    print("💡 To fetch from OMDb API, run:")
    print("   python -m app.backend.ingestion.movies.fetch_movies")
    print("   Then edit fetch_movies.py to add your titles to the list")


if __name__ == "__main__":
    asyncio.run(main())
