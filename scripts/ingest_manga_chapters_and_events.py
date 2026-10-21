import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from pymongo import UpdateOne

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.mongo import connect_db, get_db, close_db
from app.repositories.event_repository import get_today_events
from app.repositories.home_repository import get_today_chapter_anniversaries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ingest_manga_chapters_and_events")

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

MANGA_METADATA = {
    "one_piece": {"manga_id": "manga_one_piece", "title": "One Piece", "author": "Eiichiro Oda"},
    "naruto": {"manga_id": "manga_naruto", "title": "Naruto", "author": "Masashi Kishimoto"},
    "bleach": {"manga_id": "manga_bleach", "title": "Bleach", "author": "Tite Kubo"},
    "attack_on_titan": {"manga_id": "manga_attack_on_titan", "title": "Attack on Titan", "author": "Hajime Isayama"},
    "dragon_ball": {"manga_id": "manga_dragon_ball", "title": "Dragon Ball", "author": "Akira Toriyama"},
    "demon_slayer": {"manga_id": "manga_demon_slayer", "title": "Demon Slayer", "author": "Koyoharu Gotouge"},
    "jujutsu_kaisen": {"manga_id": "manga_jujutsu_kaisen", "title": "Jujutsu Kaisen", "author": "Gege Akutami"},
    "my_hero_academia": {"manga_id": "manga_my_hero_academia", "title": "My Hero Academia", "author": "Kohei Horikoshi"},
    "chainsaw_man": {"manga_id": "manga_chainsaw_man", "title": "Chainsaw Man", "author": "Tatsuki Fujimoto"},
    "fullmetal_alchemist": {"manga_id": "manga_fullmetal_alchemist", "title": "Fullmetal Alchemist", "author": "Hiromu Arakawa"},
    "spy_x_family": {"manga_id": "manga_spy_x_family", "title": "Spy x Family", "author": "Tatsuya Endo"},
    "tokyo_ghoul": {"manga_id": "manga_tokyo_ghoul", "title": "Tokyo Ghoul", "author": "Sui Ishida"},
    "hunter_x_hunter": {"manga_id": "manga_hunter_x_hunter", "title": "Hunter x Hunter", "author": "Yoshihiro Togashi"},
}

def parse_date(raw: str):
    """
    Parses varied fandom release date formats into (iso_str, year, month, day).
    Supports:
      - 'July 19, 1997'
      - 'Date Released February 15th, 2016'
      - 'Release Date December 3, 2018'
      - 'Year Released: September 8, 2011'
      - '1999/10/04'
      - '1999-10-04'
    """
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    s = re.sub(r"^(date released|release date|year released:?)\s*", "", s, flags=re.I).strip()
    s = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s, flags=re.I)

    # 1. YYYY/MM/DD or YYYY-MM-DD
    m1 = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m1:
        y, m, d = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        return f"{y:04d}-{m:02d}-{d:02d}", y, m, d

    # 2. Month D, YYYY
    m2 = re.search(r"([a-zA-Z]+)\s+(\d{1,2}),?\s+(\d{4})", s)
    if m2:
        month_name = m2.group(1).lower()
        if month_name in MONTHS:
            m = MONTHS[month_name]
            d = int(m2.group(2))
            y = int(m2.group(3))
            return f"{y:04d}-{m:02d}-{d:02d}", y, m, d

    # 3. D Month YYYY
    m3 = re.search(r"(\d{1,2})\s+([a-zA-Z]+),?\s+(\d{4})", s)
    if m3:
        month_name = m3.group(2).lower()
        if month_name in MONTHS:
            d = int(m3.group(1))
            m = MONTHS[month_name]
            y = int(m3.group(3))
            return f"{y:04d}-{m:02d}-{d:02d}", y, m, d

    return None

async def ingest_manga_dataset():
    logger.info("=" * 80)
    logger.info("INGESTING MANGA CHAPTERS AND CONNECTING TO TODAY'S EVENTS")
    logger.info("=" * 80)

    await connect_db()
    db = get_db()

    data_dir = PROJECT_ROOT / "data" / "manga_chapters"
    json_files = sorted(list(data_dir.glob("*_chapters.json")))
    logger.info(f"Discovered {len(json_files)} manga chapter datasets in {data_dir}")

    total_chapters_upserted = 0
    total_events_upserted = 0

    for jf in json_files:
        manga_slug = jf.stem.replace("_chapters", "")
        meta = MANGA_METADATA.get(manga_slug, {
            "manga_id": f"manga_{manga_slug}",
            "title": manga_slug.replace("_", " ").title(),
            "author": "Unknown Author"
        })
        manga_id = meta["manga_id"]
        series_title = meta["title"]

        with open(jf, "r", encoding="utf-8") as f:
            chapters = json.load(f)

        if not chapters:
            continue

        # 1. Ensure parent record in 'manga' collection
        await db["manga"].update_one(
            {"_id": manga_id},
            {
                "$setOnInsert": {
                    "_id": manga_id,
                    "name": series_title,
                    "title": {"english": series_title, "romaji": series_title},
                    "author": meta["author"],
                    "type": "MANGA",
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

        chapter_ops = []
        event_ops = []

        for ch in chapters:
            ch_num = ch.get("chapter_number")
            if ch_num is None:
                continue

            raw_date = ch.get("release_date")
            parsed = parse_date(raw_date)
            normalized_date = parsed[0] if parsed else raw_date

            # Clean and prepare character appearances
            raw_chars = ch.get("characters_appeared") or []
            char_ids = ch.get("character_ids") or []
            if not char_ids and raw_chars:
                for c in raw_chars:
                    if isinstance(c, dict) and c.get("slug"):
                        char_ids.append(c["slug"])
                    elif isinstance(c, str):
                        clean_slug = "char_" + re.sub(r"[^a-z0-9_]+", "", c.lower().replace(" ", "_"))
                        char_ids.append(clean_slug)

            ch_id = ch.get("_id") or f"chapter_{manga_slug}_{ch_num}"
            ch_title = ch.get("title") or f"Chapter {ch_num}"

            chapter_doc = {
                "_id": ch_id,
                "manga_id": manga_id,
                "series_id": manga_id,
                "series_title": series_title,
                "chapter_number": ch_num,
                "title": ch_title,
                "volume": ch.get("volume"),
                "arc": ch.get("arc"),
                "release_date": normalized_date,
                "summary": ch.get("summary") or "",
                "characters_appeared": raw_chars,
                "character_ids": char_ids,
                "source_url": ch.get("source_url") or "",
                "is_deleted": False,
                "updated_at": datetime.now(timezone.utc),
            }

            ch_doc_set = dict(chapter_doc)
            ch_doc_set.pop("_id", None)

            chapter_ops.append(
                UpdateOne(
                    {"manga_id": manga_id, "chapter_number": ch_num},
                    {"$set": ch_doc_set, "$setOnInsert": {"_id": ch_id}},
                    upsert=True,
                )
            )

            # 2. Create Event Record in 'events' collection if valid calendar date exists
            if parsed:
                iso_date, year, month, day = parsed
                event_id = f"event_{ch_id}"
                
                # Descriptive title and summary
                event_title = f"{series_title} Chapter {ch_num} Released"
                first_few_chars = [c.get("name") for c in raw_chars[:3] if isinstance(c, dict) and c.get("name")]
                feat_str = f" Features {', '.join(first_few_chars)}." if first_few_chars else ""
                event_desc = (
                    f"{series_title} Chapter {ch_num}: '{ch_title}' was officially published on this day in {year}.{feat_str}"
                )

                event_doc = {
                    "title": event_title,
                    "description": event_desc,
                    "month": month,
                    "day": day,
                    "year": year,
                    "event_type": "manga_release",
                    "anime_id": None,
                    "manga_id": manga_id,
                    "chapter_id": ch_id,
                    "chapter_number": ch_num,
                    "chapter_title": ch_title,
                    "character_ids": char_ids,
                    "release_date": iso_date,
                    "summary": (ch.get("summary") or "")[:500],
                    "tags": [manga_slug, "manga", f"chapter_{ch_num}"],
                    "is_deleted": False,
                    "deleted_at": None,
                    "updated_at": datetime.now(timezone.utc),
                }

                event_ops.append(
                    UpdateOne(
                        {"_id": event_id},
                        {"$set": event_doc, "$setOnInsert": {"_id": event_id}},
                        upsert=True,
                    )
                )

        # Batch execute chapter upserts
        if chapter_ops:
            batch_size = 500
            for i in range(0, len(chapter_ops), batch_size):
                chunk = chapter_ops[i:i + batch_size]
                res = await db["chapters"].bulk_write(chunk, ordered=False)
                total_chapters_upserted += (res.upserted_count + res.modified_count)

        # Batch execute event upserts
        if event_ops:
            batch_size = 500
            for i in range(0, len(event_ops), batch_size):
                chunk = event_ops[i:i + batch_size]
                res = await db["events"].bulk_write(chunk, ordered=False)
                total_events_upserted += (res.upserted_count + res.modified_count)

        logger.info(
            f"[{series_title}] Synced {len(chapter_ops)} chapters and {len(event_ops)} calendar events."
        )

    logger.info("=" * 80)
    logger.info(f"TOTAL CHAPTERS PROCESSED: {total_chapters_upserted}")
    logger.info(f"TOTAL CALENDAR EVENTS PROCESSED: {total_events_upserted}")
    logger.info("=" * 80)

    # 3. VERIFICATION & TODAY'S EVENT LINK CHECK
    logger.info("\n--- VERIFYING TODAY'S EVENTS AND ANNIVERSARIES ---")
    today = datetime.utcnow()
    logger.info(f"Current UTC Date: {today.strftime('%Y-%m-%d')} (Month: {today.month}, Day: {today.day})")

    # A. Check /events/today
    today_events = await get_today_events()
    chapter_events_today = [e for e in today_events if e.get("event_type") == "manga_release" or e.get("chapter_number")]
    logger.info(f"Total events today in db['events']: {len(today_events)}")
    logger.info(f"Manga chapter events active today: {len(chapter_events_today)}")
    for ev in chapter_events_today[:5]:
        logger.info(f"  * [Event] {ev.get('title')} ({ev.get('year')}) - {ev.get('description')[:100]}...")

    # B. Check /home/today chapter anniversaries
    today_anniversaries = await get_today_chapter_anniversaries()
    logger.info(f"\nTotal chapter anniversaries today in /home/today: {len(today_anniversaries)}")
    for ann in today_anniversaries[:5]:
        logger.info(f"  * [Anniversary] {ann.get('parent_title')} - {ann.get('title')} ({ann.get('years_ago')} years ago, released {ann.get('release_date')})")

    # C. Verify Naruto Chapter 1 specifically as requested
    logger.info("\n--- VERIFYING NARUTO CHAPTER 1 DATA ---")
    naruto_ch1 = await db["chapters"].find_one({"manga_id": "manga_naruto", "chapter_number": 1})
    if naruto_ch1:
        logger.info(f"Found Naruto Chapter 1 in 'chapters':")
        logger.info(f"  _id: {naruto_ch1.get('_id')}")
        logger.info(f"  title: {naruto_ch1.get('title')}")
        logger.info(f"  release_date: {naruto_ch1.get('release_date')}")
        logger.info(f"  summary: {naruto_ch1.get('summary')[:120]}...")
        logger.info(f"  characters count: {len(naruto_ch1.get('characters_appeared', []))}")
        logger.info(f"  character_ids: {naruto_ch1.get('character_ids')[:5]}...")

    naruto_event = await db["events"].find_one({"manga_id": "manga_naruto", "chapter_number": 1})
    if naruto_event:
        logger.info(f"\nFound Naruto Chapter 1 in 'events':")
        logger.info(f"  _id: {naruto_event.get('_id')}")
        logger.info(f"  title: {naruto_event.get('title')}")
        logger.info(f"  month/day/year: {naruto_event.get('month')}/{naruto_event.get('day')}/{naruto_event.get('year')}")
        logger.info(f"  event_type: {naruto_event.get('event_type')}")
        logger.info(f"  description: {naruto_event.get('description')}")
        logger.info(f"  connected chapter_id: {naruto_event.get('chapter_id')}")

    await close_db()
    logger.info("\nIngestion and Verification Complete!")

if __name__ == "__main__":
    asyncio.run(ingest_manga_dataset())
