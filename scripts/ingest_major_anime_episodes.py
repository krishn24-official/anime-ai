import argparse
import asyncio
import io
import json
import logging
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 encoding with unbuffered lines
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bs4 import BeautifulSoup
from pymongo import UpdateOne
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db.mongo import close_db, connect_db, get_db
from app.repositories import lore_repository
from app.services import lore_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ingest_major_anime")

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

SERIES_DEFINITIONS = {
    "demon_slayer": {
        "anime_id": "anime_demon_slayer",
        "slug": "demon_slayer",
        "title": "Demon Slayer: Kimetsu no Yaiba",
        "author": "Koyoharu Gotouge",
        "romaji": "Kimetsu no Yaiba",
        "japanese": "鬼滅の刃",
        "api_endpoint": "https://kimetsu-no-yaiba.fandom.com/api.php",
        "mode": "numbered",
        "max_episodes": 63,
    },
    "jujutsu_kaisen": {
        "anime_id": "anime_jujutsu_kaisen",
        "slug": "jujutsu_kaisen",
        "title": "Jujutsu Kaisen",
        "author": "Gege Akutami",
        "romaji": "Jujutsu Kaisen",
        "japanese": "呪術廻戦",
        "api_endpoint": "https://jujutsu-kaisen.fandom.com/api.php",
        "mode": "numbered",
        "max_episodes": 47,
    },
    "attack_on_titan": {
        "anime_id": "anime_attack_on_titan",
        "slug": "attack_on_titan",
        "title": "Attack on Titan",
        "author": "Hajime Isayama",
        "romaji": "Shingeki no Kyojin",
        "japanese": "進撃の巨人",
        "api_endpoint": "https://attackontitan.fandom.com/api.php",
        "mode": "category",
        "category": "Category:Episodes",
    },
    "bleach": {
        "anime_id": "anime_bleach",
        "slug": "bleach",
        "title": "Bleach",
        "author": "Tite Kubo",
        "romaji": "Bleach",
        "japanese": "BLEACH",
        "api_endpoint": "https://bleach.fandom.com/api.php",
        "mode": "category",
        "category": "Category:Episodes",
    },
    "one_piece": {
        "anime_id": "anime_one_piece",
        "slug": "one_piece",
        "title": "One Piece",
        "author": "Eiichiro Oda",
        "romaji": "One Piece",
        "japanese": "ONE PIECE",
        "api_endpoint": "https://onepiece.fandom.com/api.php",
        "mode": "numbered",
        "max_episodes": 1120,
    },
}


def parse_date(raw: str):
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    s = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s, flags=re.I)

    # 1. YYYY/MM/DD or YYYY-MM-DD
    m1 = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m1:
        y, m, d = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        return f"{y:04d}-{m:02d}-{d:02d}", y, m, d

    # 2. D Month YYYY
    m2 = re.search(r"(\d{1,2})\s+([a-zA-Z]+),?\s+(\d{4})", s)
    if m2:
        month_name = m2.group(2).lower()
        if month_name in MONTHS:
            d = int(m2.group(1))
            m = MONTHS[month_name]
            y = int(m2.group(3))
            return f"{y:04d}-{m:02d}-{d:02d}", y, m, d

    # 3. Month D, YYYY
    m3 = re.search(r"([a-zA-Z]+)\s+(\d{1,2}),?\s+(\d{4})", s)
    if m3:
        month_name = m3.group(1).lower()
        if month_name in MONTHS:
            m = MONTHS[month_name]
            d = int(m3.group(2))
            y = int(m3.group(3))
            return f"{y:04d}-{m:02d}-{d:02d}", y, m, d

    return None


def fetch_mediawiki_page(endpoint: str, page_title: str) -> dict:
    encoded = urllib.parse.quote(page_title.replace(" ", "_"))
    url = f"{endpoint}?action=parse&page={encoded}&prop=wikitext&format=json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnimeAI/1.0"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("parse", {})
        except Exception:
            if attempt == 2:
                return {}
            time.sleep(1.0)
    return {}


def fetch_category_pages(endpoint: str, category_name: str) -> list[str]:
    pages = []
    cmcontinue = None
    while True:
        url = f"{endpoint}?action=query&list=categorymembers&cmtitle={urllib.parse.quote(category_name)}&cmlimit=500&format=json"
        if cmcontinue:
            url += f"&cmcontinue={cmcontinue}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnimeAI/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                members = data.get("query", {}).get("categorymembers", [])
                for m in members:
                    t = m.get("title", "")
                    if not t.startswith("Category:") and not t.startswith("Template:"):
                        pages.append(t)
                cmcontinue = data.get("continue", {}).get("cmcontinue")
                if not cmcontinue:
                    break
        except Exception as e:
            logger.warning(f"Error fetching category {category_name}: {e}")
            break
    return pages


def clean_wikitext(text: str) -> str:
    if not text:
        return ""
    s = re.sub(r"<section[^>]*>", "", text)
    s = re.sub(r"</section>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", s)
    s = re.sub(r"''+", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_generic_episode_wikitext(wt: str, fallback_title: str = "", ep_num: int = 1) -> dict:
    details = {
        "episode_number": ep_num,
        "title": "",
        "kanji_title": "",
        "romaji_title": "",
        "release_date": "",
        "english_airdate": "",
        "arc": "",
        "manga_chapters_covered": None,
        "is_filler": False,
        "canon_type": "manga canon",
        "director": "",
        "summary": "",
        "characters_appeared": [],
        "character_ids": [],
    }

    if not wt:
        details["title"] = fallback_title
        return details

    for line in wt.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if "=" in line:
            k, v = line[1:].split("=", 1)
            k = k.strip().lower()
            v = v.strip()

            if k in ("title", "ep title", "episode title", "english", "name", "translation") and v:
                clean_t = clean_wikitext(v)
                if clean_t and clean_t.lower() != f"episode {ep_num}":
                    details["title"] = clean_t
            elif k in ("kanji", "japanese"):
                details["kanji_title"] = clean_wikitext(v)
            elif k in ("romaji",):
                details["romaji_title"] = clean_wikitext(v)
            elif k in ("arc", "story arc"):
                details["arc"] = clean_wikitext(v)
            elif k in ("airdate", "air_date", "air date", "japanese airdate", "original airdate", "original air date", "jp air date", "air date (ja)", "date", "japair"):
                # Clean html breaks or templates
                clean_d = clean_wikitext(re.split(r"<br\s*/?>", v)[0])
                details["release_date"] = clean_d
            elif k in ("english airdate", "english release", "eng_air_date", "us air date", "air date (us)", "engair"):
                clean_en = clean_wikitext(re.split(r"<br\s*/?>", v)[0])
                details["english_airdate"] = clean_en
            elif k in ("chapters", "manga chapters", "manga chapter", "chapter", "adapted from"):
                cleaned_ch = clean_wikitext(v)
                if cleaned_ch and cleaned_ch.lower() not in ("none", "n/a", "-"):
                    details["manga_chapters_covered"] = cleaned_ch
            elif k in ("filler", "is_filler"):
                if v.lower() in ("yes", "true", "1"):
                    details["is_filler"] = True
            elif k in ("episodenumber", "number (overall)", "episode", "number", "no", "ep number", "#"):
                try:
                    num_match = re.search(r"\b\d+\b", v)
                    if num_match:
                        details["episode_number"] = int(num_match.group(0))
                except Exception:
                    pass

    if not details["title"]:
        details["title"] = fallback_title

    # Filler determination
    if details["is_filler"]:
        details["canon_type"] = "filler"
        if not details["manga_chapters_covered"]:
            details["manga_chapters_covered"] = "Anime-Original / Filler"
    elif details["manga_chapters_covered"]:
        details["canon_type"] = "manga canon"
    else:
        details["canon_type"] = "manga canon"

    # Synopsis extraction
    syn_match = re.search(r"==\s*(?:Synopsis|Summary|Plot)\s*==\s*(.*?)(?=\n==|\Z)", wt, re.DOTALL | re.IGNORECASE)
    if syn_match:
        raw_syn = syn_match.group(1).strip()
        # Find character links
        found_chars = set()
        for char_m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", raw_syn):
            target = char_m.group(1).strip()
            if not any(target.lower().startswith(p) for p in ("category:", "file:", "image:", "help:")):
                found_chars.add(target)

        for c in sorted(list(found_chars))[:20]:
            clean_slug = "char_" + re.sub(r"[^a-z0-9_]+", "", c.lower().replace(" ", "_"))
            details["characters_appeared"].append(c)
            details["character_ids"].append(clean_slug)

        details["summary"] = clean_wikitext(raw_syn)

    return details


def generate_episode_lore_pdf(series_title: str, episodes: list[dict], output_pdf_path: Path):
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=letter,
        leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=colors.HexColor("#1A202C"),
        alignment=1,
        spaceAfter=12,
    )
    subtitle_style = ParagraphStyle(
        "CoverSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#4A5568"),
        alignment=1,
        spaceAfter=20,
    )
    h1_style = ParagraphStyle(
        "EpHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    meta_style = ParagraphStyle(
        "EpMeta", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.HexColor("#2D3748")
    )
    meta_val_style = ParagraphStyle(
        "EpMetaVal", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#4A5568")
    )
    body_style = ParagraphStyle(
        "EpBody", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13, textColor=colors.HexColor("#2D3748"), spaceBefore=3, spaceAfter=8
    )

    story = [
        Spacer(1, 30),
        Paragraph(f"{series_title}", title_style),
        Paragraph("Complete Animated Series Canon Guide & Episode Compendium", subtitle_style),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#3182CE"), spaceBefore=10, spaceAfter=20),
        Paragraph(f"Official lore book indexing all {len(episodes)} episodes of {series_title}, including original broadcast air dates, manga chapters covered, story arcs, and comprehensive narrative synopses.", body_style),
        PageBreak()
    ]

    for ep in episodes:
        ep_num = ep["episode_number"]
        ep_title = ep["title"] or f"Episode {ep_num}"
        arc = ep.get("arc") or "General"
        ch_cov = ep.get("manga_chapters_covered") or ("Anime-Original / Filler" if ep.get("is_filler") else "Manga Canon")
        airdate = ep.get("release_date") or "Unknown"
        en_airdate = ep.get("english_airdate") or "N/A"
        canon_status = "Filler (Anime Original)" if ep.get("is_filler") else "Canon (Manga Adaptation)"
        chars = ", ".join(ep.get("characters_appeared", [])[:10]) or "Featured cast"
        synopsis = ep.get("summary") or "Detailed synopsis unavailable."

        if len(synopsis) > 2200:
            synopsis = synopsis[:2200] + "..."

        ep_elements = [
            Paragraph(f"Episode {ep_num}: {ep_title}", h1_style),
            Table([
                [Paragraph("Story Arc:", meta_style), Paragraph(arc, meta_val_style), Paragraph("Release Date:", meta_style), Paragraph(airdate, meta_val_style)],
                [Paragraph("Canon Status:", meta_style), Paragraph(canon_status, meta_val_style), Paragraph("English Airdate:", meta_style), Paragraph(en_airdate, meta_val_style)],
                [Paragraph("Manga Covered:", meta_style), Paragraph(str(ch_cov), meta_val_style), Paragraph("Characters:", meta_style), Paragraph(chars, meta_val_style)],
            ], colWidths=[80, 180, 80, 180]),
            Spacer(1, 3),
            Paragraph(f"<b>Synopsis:</b> {synopsis}", body_style),
            HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E0"), spaceBefore=4, spaceAfter=6),
        ]
        story.append(KeepTogether(ep_elements))

    doc.build(story)
    logger.info(f"Generated PDF lore book: {output_pdf_path} ({output_pdf_path.stat().st_size} bytes)")


async def process_series(slug: str, cfg: dict, output_dir: Path):
    logger.info("=" * 80)
    logger.info(f"PROCESSING ANIME: {cfg['title']} ({slug.upper()})")
    logger.info("=" * 80)

    endpoint = cfg["api_endpoint"]
    episodes_to_fetch = []

    if cfg["mode"] == "numbered":
        max_eps = cfg["max_episodes"]
        for i in range(1, max_eps + 1):
            episodes_to_fetch.append({"page_title": f"Episode {i}", "episode_number": i})
    elif cfg["mode"] == "category":
        pages = fetch_category_pages(endpoint, cfg["category"])
        logger.info(f"[{cfg['title']}] Discovered {len(pages)} episode pages in category.")
        for p in pages:
            # Estimate episode number from title or default
            num_match = re.search(r"\bEpisode\s+(\d+)\b", p, re.I)
            ep_num = int(num_match.group(1)) if num_match else len(episodes_to_fetch) + 1
            episodes_to_fetch.append({"page_title": p, "episode_number": ep_num})

    logger.info(f"[{cfg['title']}] Concurrently fetching {len(episodes_to_fetch)} episodes from {endpoint}...")

    episodes_detailed = []
    with ThreadPoolExecutor(max_workers=14) as executor:
        future_to_ep = {
            executor.submit(fetch_mediawiki_page, endpoint, ep["page_title"]): ep
            for ep in episodes_to_fetch
        }
        done = 0
        for future in as_completed(future_to_ep):
            ep = future_to_ep[future]
            done += 1
            try:
                res = future.result()
                wt = res.get("wikitext", {}).get("*", "")
                page_title = res.get("title", ep["page_title"])
            except Exception:
                wt = ""
                page_title = ep["page_title"]

            parsed = parse_generic_episode_wikitext(wt, fallback_title=page_title, ep_num=ep["episode_number"])

            raw_date = parsed["release_date"]
            parsed_d = parse_date(raw_date)
            normalized_date = parsed_d[0] if parsed_d else raw_date

            ep_id = f"ep_{slug}_{parsed['episode_number']}"

            # Map covered manga chapters
            manga_ch_list = []
            if parsed["manga_chapters_covered"] and not parsed["is_filler"]:
                ch_nums = re.findall(r"\b\d+\b", str(parsed["manga_chapters_covered"]))
                for cnum in ch_nums:
                    manga_ch_list.append(f"ch_{cnum}")

            episode_doc = {
                "_id": ep_id,
                "anime_id": cfg["anime_id"],
                "series_id": cfg["anime_id"],
                "anime_title": cfg["title"],
                "anime_slug": slug,
                "episode_number": parsed["episode_number"],
                "title": parsed["title"],
                "kanji_title": parsed["kanji_title"],
                "romaji_title": parsed["romaji_title"],
                "release_date": normalized_date,
                "english_airdate": parsed["english_airdate"],
                "director": parsed["director"],
                "arc": parsed["arc"],
                "is_filler": parsed["is_filler"],
                "canon_type": parsed["canon_type"],
                "manga_chapters_covered": parsed["manga_chapters_covered"],
                "manga_chapters": manga_ch_list,
                "summary": parsed["summary"],
                "characters_appeared": parsed["characters_appeared"],
                "character_ids": parsed["character_ids"],
                "wiki_page": ep["page_title"],
                "is_deleted": False,
                "deleted_at": None,
                "updated_at": datetime.now(timezone.utc),
            }
            episodes_detailed.append(episode_doc)

            if done % 50 == 0 or done == len(episodes_to_fetch):
                logger.info(f"[{cfg['title']}] Progress: {done}/{len(episodes_to_fetch)} episodes fetched.")

    episodes_detailed.sort(key=lambda x: x["episode_number"])

    # 1. Save JSON
    json_path = output_dir / f"{slug}_episodes.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(episodes_detailed, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"[{cfg['title']}] Saved {len(episodes_detailed)} episodes to {json_path}")

    # 2. Generate PDF Lore Book
    pdf_path = output_dir / f"{slug}_episodes_lore.pdf"
    generate_episode_lore_pdf(cfg["title"], episodes_detailed, pdf_path)

    # 3. Upsert to MongoDB Atlas
    db = get_db()

    # Ensure parent anime record
    await db["anime"].update_one(
        {"_id": cfg["anime_id"]},
        {
            "$setOnInsert": {
                "_id": cfg["anime_id"],
                "title": {
                    "english": cfg["title"],
                    "romaji": cfg["romaji"],
                    "japanese": cfg["japanese"],
                },
                "slug": slug,
                "type": "TV",
                "episodes": len(episodes_detailed),
                "created_at": datetime.now(timezone.utc),
                "is_deleted": False,
            }
        },
        upsert=True,
    )

    ep_ops = []
    event_ops = []
    for ep in episodes_detailed:
        ep_id = ep["_id"]
        ep_set = dict(ep)
        ep_set.pop("_id", None)

        ep_ops.append(
            UpdateOne(
                {"anime_id": cfg["anime_id"], "episode_number": ep["episode_number"]},
                {"$set": ep_set, "$setOnInsert": {"_id": ep_id}},
                upsert=True,
            )
        )

        pdate = parse_date(ep["release_date"])
        if pdate:
            iso_date, y, m, d = pdate
            ev_id = f"event_{ep_id}"
            ev_doc = {
                "title": f"{cfg['title']} Episode {ep['episode_number']} Aired",
                "description": f"{cfg['title']} Episode {ep['episode_number']}: '{ep['title']}' broadcast in Japan in {y}.",
                "month": m,
                "day": d,
                "year": y,
                "event_type": "anime_release",
                "anime_id": cfg["anime_id"],
                "episode_id": ep_id,
                "episode_number": ep["episode_number"],
                "release_date": iso_date,
                "summary": (ep.get("summary") or "")[:500],
                "tags": [slug, "anime", f"episode_{ep['episode_number']}"],
                "is_deleted": False,
                "deleted_at": None,
                "updated_at": datetime.now(timezone.utc),
            }
            event_ops.append(
                UpdateOne(
                    {"_id": ev_id},
                    {"$set": ev_doc, "$setOnInsert": {"_id": ev_id}},
                    upsert=True,
                )
            )

    if ep_ops:
        for i in range(0, len(ep_ops), 500):
            await db["episodes"].bulk_write(ep_ops[i:i + 500], ordered=False)
    if event_ops:
        for i in range(0, len(event_ops), 500):
            await db["events"].bulk_write(event_ops[i:i + 500], ordered=False)

    logger.info(f"[{cfg['title']}] Upserted {len(ep_ops)} episodes and {len(event_ops)} calendar events to MongoDB Atlas.")

    # 4. Train RAG Vector Model
    if pdf_path.exists():
        logger.info(f"[{cfg['title']}] Ingesting PDF into RAG vector search...")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        chunks = lore_service.process_lore_pdf(
            file_bytes=pdf_bytes,
            series_id=cfg["anime_id"],
            character_ids=None,
            source_file=pdf_path.name,
        )
        logger.info(f"[{cfg['title']}] Generated {len(chunks)} embedded vector chunks.")

        await connect_db()
        deleted = await lore_repository.delete_by_series(cfg["anime_id"])
        if deleted > 0:
            logger.info(f"[{cfg['title']}] Cleared {deleted} previous chunks.")

        await lore_repository.insert_chunks(chunks)
        logger.info(f"[{cfg['title']}] Ingested {len(chunks)} chunks into 'lore_chunks' collection!")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--series", type=str, default="demon_slayer,jujutsu_kaisen,attack_on_titan", help="Comma-separated series slugs")
    args = parser.parse_args()

    selected_slugs = [s.strip() for s in args.series.split(",") if s.strip()]

    data_dir = PROJECT_ROOT / "data" / "anime_episodes"
    data_dir.mkdir(parents=True, exist_ok=True)

    await connect_db()

    for slug in selected_slugs:
        if slug in SERIES_DEFINITIONS:
            await process_series(slug, SERIES_DEFINITIONS[slug], data_dir)
        else:
            logger.error(f"Unknown series slug: {slug}")

    await close_db()
    logger.info("ALL REQUESTED ANIME PROCESSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
