import asyncio
import io
import json
import re
import sys
from pathlib import Path

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.mongo import connect_db, get_db, close_db

EXPLICIT_GENRES = ["Hentai", "Erotica", "Pornographic", "Adult"]
ADULT_RATINGS = ["Rx", "R18", "R18+", "18+", "NC-17", "Adult", "Rx - Hentai"]

EXPLICIT_KEYWORD_PATTERNS = [
    r"\bhentai\b",
    r"\bjav\b",
    r"\bporn\b",
    r"\beroge\b",
    r"\bsex\b",
    r"\bblowjob\b",
    r"\bcreampie\b",
    r"\bmilf\b",
    r"\bahegao\b",
    r"\bnetorare\b",
    r"\bntr\b",
    r"\bbitch ni\b",
    r"\bshiboraretai\b",
    r"\bfutanari\b",
    r"\byaOI 18\+\b",
]
KEYWORD_REGEX = re.compile("|".join(EXPLICIT_KEYWORD_PATTERNS), re.IGNORECASE)

async def scan():
    await connect_db()
    db = get_db()
    colls = sorted(await db.list_collection_names())
    
    print("=" * 80)
    print("COMPREHENSIVE ADULT CONTENT DATABASE SCAN")
    print("=" * 80)

    summary = {}

    for coll in colls:
        found_docs = []
        try:
            # Query for explicit boolean flags
            flag_query = {
                "$or": [
                    {"is_adult": True},
                    {"adult": True},
                    {"isAdult": True},
                    {"is_nsfw": True},
                    {"nsfw": True},
                    {"genres": {"$in": EXPLICIT_GENRES}},
                    {"genre": {"$in": EXPLICIT_GENRES}},
                    {"tags": {"$in": EXPLICIT_GENRES}},
                    {"rating": {"$in": ADULT_RATINGS}},
                    {"content_rating": {"$in": ADULT_RATINGS}},
                    {"age_rating": {"$in": ADULT_RATINGS}},
                    {"source_metadata.adult": True},
                    {"source_metadata.isAdult": True},
                ]
            }

            cursor = db[coll].find(flag_query)
            async for doc in cursor:
                found_docs.append({
                    "_id": str(doc.get("_id")),
                    "reason": "explicit_flag",
                    "title": doc.get("title") or doc.get("name") or doc.get("headline"),
                    "genres": doc.get("genres") or doc.get("tags"),
                    "rating": doc.get("rating") or doc.get("content_rating"),
                })

            # In content collections, also check title keywords
            if coll in ["anime", "manga", "movies", "tv_series", "news", "events", "trending_content", "episodes"]:
                title_cursor = db[coll].find({
                    "$or": [
                        {"title": {"$type": "string"}},
                        {"title.english": {"$type": "string"}},
                        {"title.romaji": {"$type": "string"}},
                        {"name": {"$type": "string"}},
                    ]
                }, {"_id": 1, "title": 1, "name": 1, "genres": 1, "rating": 1})

                already_ids = {d["_id"] for d in found_docs}
                async for doc in title_cursor:
                    doc_id = str(doc.get("_id"))
                    if doc_id in already_ids:
                        continue
                    t = doc.get("title")
                    title_str = ""
                    if isinstance(t, str):
                        title_str = t
                    elif isinstance(t, dict):
                        title_str = " ".join([str(v) for v in t.values() if isinstance(v, str)])
                    if doc.get("name"):
                        title_str += " " + str(doc.get("name"))

                    if KEYWORD_REGEX.search(title_str):
                        found_docs.append({
                            "_id": doc_id,
                            "reason": "keyword_match",
                            "title": title_str,
                            "genres": doc.get("genres"),
                            "rating": doc.get("rating"),
                        })

        except Exception as e:
            print(f"Error scanning {coll}: {e}")

        summary[coll] = found_docs
        print(f"Collection: {coll:<22} | Detected: {len(found_docs)}")

    print("\n" + "=" * 80)
    print("DETAILED BREAKDOWN OF SUSPICIOUS / ADULT CONTENT")
    print("=" * 80)
    for coll, items in summary.items():
        if items:
            print(f"\n[{coll}] ({len(items)} items):")
            for item in items[:15]:
                print(f"  - ID: {item['_id']} | Title: {str(item['title'])[:50]} | Reason: {item['reason']} | Genres: {item['genres']} | Rating: {item['rating']}")
            if len(items) > 15:
                print(f"  ... and {len(items) - 15} more.")

    # Save complete scan report to json
    report_path = PROJECT_ROOT / "scratch" / "adult_scan_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nFull scan report saved to: {report_path}")

    await close_db()

if __name__ == "__main__":
    asyncio.run(scan())
