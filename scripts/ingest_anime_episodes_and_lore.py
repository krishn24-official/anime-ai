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

# Force UTF-8 stdout/stderr for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

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
logger = logging.getLogger("ingest_anime_episodes")

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

SERIES_CONFIG = [
    {
        "table_index": 0,
        "anime_id": "anime_naruto",
        "slug": "naruto",
        "title": "Naruto",
        "expected_episodes": 220,
        "author": "Masashi Kishimoto",
        "romaji": "Naruto",
        "japanese": "NARUTO -ナルト-",
    },
    {
        "table_index": 1,
        "anime_id": "anime_naruto_shippuden",
        "slug": "naruto_shippuden",
        "title": "Naruto: Shippūden",
        "expected_episodes": 500,
        "author": "Masashi Kishimoto",
        "romaji": "Naruto: Shippūden",
        "japanese": "NARUTO -ナルト- 疾風伝",
    },
    {
        "table_index": 2,
        "anime_id": "anime_boruto",
        "slug": "boruto",
        "title": "Boruto: Naruto Next Generations",
        "expected_episodes": 293,
        "author": "Ukyō Kodachi / Masashi Kishimoto",
        "romaji": "Boruto: Naruto Next Generations",
        "japanese": "BORUTO-ボルト- NARUTO NEXT GENERATIONS",
    },
]


def parse_date(raw: str):
    """
    Parses varied release date strings into (iso_str, year, month, day).
    Supports:
      - '3 October 2002'
      - 'October 3, 2002'
      - '2002/10/03'
      - '2002-10-03'
    """
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    s = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s, flags=re.I)

    # 1. YYYY/MM/DD or YYYY-MM-DD
    m1 = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m1:
        y, m, d = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        return f"{y:04d}-{m:02d}-{d:02d}", y, m, d

    # 2. D Month YYYY (standard Fandom format: '3 October 2002')
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


def fetch_mediawiki_page(page_title: str) -> dict:
    """Fetches wikitext and metadata for a single page from Naruto Fandom API."""
    encoded = urllib.parse.quote(page_title.replace(" ", "_"))
    url = f"https://naruto.fandom.com/api.php?action=parse&page={encoded}&prop=wikitext&format=json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnimeAI/1.0"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("parse", {})
        except Exception as e:
            if attempt == 2:
                logger.warning(f"Failed to fetch {page_title}: {e}")
                return {}
            time.sleep(1.0)
    return {}


def clean_wikitext_markup(text: str) -> str:
    """Strips internal wiki formatting, template tags, and HTML tags."""
    if not text:
        return ""
    # Remove HTML tags & section markers
    s = re.sub(r"<section[^>]*>", "", text)
    s = re.sub(r"</section>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    # Remove ref tags and templates like {{...}}
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    # Replace [[Link|Label]] -> Label and [[Link]] -> Link
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)
    # Remove external links [http... text] -> text
    s = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", s)
    # Remove bold and italic markers
    s = re.sub(r"''+", "", s)
    # Collapse excess whitespace
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_episode_wikitext(wt: str, fallback_title: str = "") -> dict:
    """Extracts infobox fields, manga chapter coverage, characters, and synopsis."""
    details = {
        "title": fallback_title,
        "kanji_title": "",
        "romaji_title": "",
        "arc": "",
        "manga_chapters_covered": None,
        "is_filler": False,
        "canon_type": "manga canon",
        "director": "",
        "english_airdate": "",
        "summary": "",
        "characters_appeared": [],
        "character_ids": [],
    }

    if not wt:
        return details

    # Extract infobox lines
    for line in wt.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue

        if "=" in line:
            key, val = line[1:].split("=", 1)
            key = key.strip().lower()
            val = val.strip()

            if key == "english" and val:
                details["title"] = val
            elif key == "kanji" and val:
                details["kanji_title"] = val
            elif key == "romaji" and val:
                details["romaji_title"] = val
            elif key == "arc" and val:
                details["arc"] = clean_wikitext_markup(val)
            elif key == "director" and val:
                details["director"] = clean_wikitext_markup(val)
            elif key in ("chapters", "manga chapters") and val:
                cleaned_val = clean_wikitext_markup(val)
                if cleaned_val and cleaned_val.lower() not in ("none", "n/a", "-"):
                    details["manga_chapters_covered"] = cleaned_val
            elif key in ("filler", "is_filler"):
                if val.lower() in ("yes", "true", "1"):
                    details["is_filler"] = True
            elif key == "english airdate" and val:
                details["english_airdate"] = val

    # Canon / Filler determination
    if details["is_filler"] or not details["manga_chapters_covered"]:
        details["is_filler"] = True
        details["canon_type"] = "filler"
        if not details["manga_chapters_covered"]:
            details["manga_chapters_covered"] = "Anime-Original / Filler"
    else:
        details["canon_type"] = "manga canon"

    # Extract Synopsis
    syn_match = re.search(r"==\s*Synopsis\s*==\s*(.*?)(?=\n==|\Z)", wt, re.DOTALL)
    if syn_match:
        raw_syn = syn_match.group(1).strip()

        # Extract character mentions from wiki links in synopsis: [[Naruto Uzumaki|Naruto]] or [[Naruto Uzumaki]]
        found_chars = set()
        for char_match in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", raw_syn):
            target = char_match.group(1).strip()
            # Filter out non-character wiki pages
            if not any(target.lower().startswith(prefix) for prefix in ("category:", "file:", "image:", "help:", "wikipedia:")):
                found_chars.add(target)

        # Store characters appeared
        for c in sorted(list(found_chars))[:20]:
            clean_slug = "char_" + re.sub(r"[^a-z0-9_]+", "", c.lower().replace(" ", "_"))
            details["characters_appeared"].append(c)
            details["character_ids"].append(clean_slug)

        details["summary"] = clean_wikitext_markup(raw_syn)

    return details


def scrape_all_episodes(output_dir: Path):
    """Parses List_of_Animated_Media HTML and fetches all 1,013 episode details."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_file = output_dir / "all_episodes_scraped_cache.json"

    if cache_file.exists():
        logger.info(f"Loading cached episode dataset from {cache_file}...")
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    logger.info("Fetching master episode table from List_of_Animated_Media...")
    url = "https://naruto.fandom.com/api.php?action=parse&page=List_of_Animated_Media&prop=text&format=json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnimeAI/1.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        html = data.get("parse", {}).get("text", {}).get("*", "")

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    logger.info(f"Located {len(tables)} tables on master page.")

    series_data = {}

    for cfg in SERIES_CONFIG:
        idx = cfg["table_index"]
        if idx >= len(tables):
            logger.error(f"Table index {idx} not found for {cfg['title']}")
            continue

        table = tables[idx]
        rows = table.find_all("tr")[1:]  # skip header row
        logger.info(f"[{cfg['title']}] Found {len(rows)} raw rows in table.")

        episodes_to_fetch = []
        for r in rows:
            cells = [td.get_text(strip=True) for td in r.find_all(["td", "th"])]
            if not cells or len(cells) < 2:
                continue

            ep_num_raw = cells[0].strip()
            try:
                ep_num = int(re.sub(r"[^\d]", "", ep_num_raw))
            except ValueError:
                continue

            raw_title = cells[1].strip().strip('"')
            jp_airdate = cells[2].strip() if len(cells) > 2 else ""
            en_airdate = cells[3].strip() if len(cells) > 3 else ""

            # Extract link to episode page
            link_tag = r.find("a")
            href = link_tag.get("href") if link_tag else ""
            page_title = href.replace("/wiki/", "").strip() if href else raw_title.replace(" ", "_")

            episodes_to_fetch.append({
                "episode_number": ep_num,
                "table_title": raw_title,
                "jp_airdate": jp_airdate,
                "en_airdate": en_airdate,
                "page_title": urllib.parse.unquote(page_title),
            })

        logger.info(f"[{cfg['title']}] Extracted {len(episodes_to_fetch)} episode entries. Concurrently fetching wikitext...")

        # Concurrently fetch detailed wikitext for each episode
        episodes_detailed = []
        batch_size = 15
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            future_to_ep = {
                executor.submit(fetch_mediawiki_page, ep["page_title"]): ep
                for ep in episodes_to_fetch
            }

            completed = 0
            for future in as_completed(future_to_ep):
                ep = future_to_ep[future]
                completed += 1
                try:
                    res = future.result()
                    wt = res.get("wikitext", {}).get("*", "")
                except Exception as e:
                    logger.warning(f"Error fetching {ep['page_title']}: {e}")
                    wt = ""

                details = parse_episode_wikitext(wt, fallback_title=ep["table_title"])

                # Determine release date (prefer Japanese airdate from table)
                parsed_jp = parse_date(ep["jp_airdate"])
                parsed_en = parse_date(ep["en_airdate"] or details["english_airdate"])

                rel_date = parsed_jp[0] if parsed_jp else ep["jp_airdate"]
                en_date = parsed_en[0] if parsed_en else (ep["en_airdate"] or details["english_airdate"])

                # Map manga chapters to chapter IDs if covered
                manga_ch_list = []
                if details["manga_chapters_covered"] and not details["is_filler"]:
                    ch_nums = re.findall(r"\b\d+\b", str(details["manga_chapters_covered"]))
                    for cnum in ch_nums:
                        manga_ch_list.append(f"ch_{cnum}")

                ep_id = f"ep_{cfg['slug']}_{ep['episode_number']}"

                episode_doc = {
                    "_id": ep_id,
                    "anime_id": cfg["anime_id"],
                    "anime_title": cfg["title"],
                    "anime_slug": cfg["slug"],
                    "episode_number": ep["episode_number"],
                    "title": details["title"] or ep["table_title"],
                    "kanji_title": details["kanji_title"],
                    "romaji_title": details["romaji_title"],
                    "release_date": rel_date,
                    "english_airdate": en_date,
                    "director": details["director"],
                    "arc": details["arc"],
                    "is_filler": details["is_filler"],
                    "canon_type": details["canon_type"],
                    "manga_chapters_covered": details["manga_chapters_covered"],
                    "manga_chapters": manga_ch_list,
                    "summary": details["summary"],
                    "characters_appeared": details["characters_appeared"],
                    "character_ids": details["character_ids"],
                    "wiki_page": ep["page_title"],
                    "is_deleted": False,
                    "deleted_at": None,
                }
                episodes_detailed.append(episode_doc)

                if completed % 50 == 0 or completed == len(episodes_to_fetch):
                    logger.info(f"[{cfg['title']}] Progress: {completed}/{len(episodes_to_fetch)} episodes fetched.")

        # Sort by episode number
        episodes_detailed.sort(key=lambda x: x["episode_number"])
        series_data[cfg["slug"]] = episodes_detailed

        # Save individual series JSON
        series_json_path = output_dir / f"{cfg['slug']}_episodes.json"
        with open(series_json_path, "w", encoding="utf-8") as f:
            json.dump(episodes_detailed, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(episodes_detailed)} episodes to {series_json_path}")

    # Save complete cache
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(series_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Master episode dataset cached at {cache_file}")

    return series_data


def generate_episode_lore_pdf(series_title: str, episodes: list[dict], output_pdf_path: Path):
    """
    Generates a PDF lore book using ReportLab.
    Each episode is formatted with clear headings, metadata tables, manga coverage,
    and synopsis suitable for dense RAG vector chunking.
    """
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=32,
        textColor=colors.HexColor("#1A202C"),
        alignment=1,  # Center
        spaceAfter=12,
    )
    subtitle_style = ParagraphStyle(
        "CoverSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#4A5568"),
        alignment=1,
        spaceAfter=24,
    )
    h1_style = ParagraphStyle(
        "EpHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )
    meta_style = ParagraphStyle(
        "EpMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2D3748"),
    )
    meta_val_style = ParagraphStyle(
        "EpMetaVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#4A5568"),
    )
    body_style = ParagraphStyle(
        "EpBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2D3748"),
        spaceBefore=4,
        spaceAfter=10,
    )

    story = []

    # Title Banner
    story.append(Spacer(1, 40))
    story.append(Paragraph(f"{series_title}", title_style))
    story.append(Paragraph("Complete Official Animated Series Episode Compendium & Canon Guide", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#3182CE"), spaceBefore=10, spaceAfter=20))

    intro_p = (
        f"This official document contains detailed episode chronicles, canon-versus-filler classifications, "
        f"original manga chapters covered, Japanese and English broadcast air dates, character appearances, "
        f"and unabridged narrative synopses for all {len(episodes)} episodes of {series_title}."
    )
    story.append(Paragraph(intro_p, body_style))
    story.append(Spacer(1, 20))
    story.append(PageBreak())

    for ep in episodes:
        ep_num = ep["episode_number"]
        ep_title = ep["title"]
        kanji = ep.get("kanji_title") or ""
        romaji = ep.get("romaji_title") or ""
        arc = ep.get("arc") or "General"
        ch_cov = ep.get("manga_chapters_covered") or ("Anime-Original / Filler" if ep.get("is_filler") else "Manga Canon")
        airdate = ep.get("release_date") or "Unknown"
        en_airdate = ep.get("english_airdate") or "N/A"
        canon_status = "Filler (Anime Original)" if ep.get("is_filler") else "Canon (Manga Adaptation)"
        chars = ", ".join(ep.get("characters_appeared", [])[:12]) or "Featured shinobi and villagers"
        synopsis = ep.get("summary") or "Comprehensive synopsis unavailable."

        # Truncate extremely long synopsis to fit comfortably while retaining narrative
        if len(synopsis) > 2500:
            synopsis = synopsis[:2500] + "..."

        ep_elements = []

        # Heading format matches RAG section patterns: "Episode {num}: {title}"
        heading_text = f"Episode {ep_num}: {ep_title}"
        if romaji and romaji != ep_title:
            heading_text += f" ({romaji})"
        ep_elements.append(Paragraph(heading_text, h1_style))

        # Metadata Table
        meta_table_data = [
            [Paragraph("Story Arc:", meta_style), Paragraph(arc, meta_val_style),
             Paragraph("Release Date:", meta_style), Paragraph(airdate, meta_val_style)],
            [Paragraph("Canon Status:", meta_style), Paragraph(canon_status, meta_val_style),
             Paragraph("English Airdate:", meta_style), Paragraph(en_airdate, meta_val_style)],
            [Paragraph("Manga Covered:", meta_style), Paragraph(str(ch_cov), meta_val_style),
             Paragraph("Japanese Title:", meta_style), Paragraph(kanji if kanji else "N/A", meta_val_style)],
            [Paragraph("Characters:", meta_style), Paragraph(f"Characters in Episode {ep_num}: {chars}", meta_val_style), "", ""],
        ]
        meta_table = Table(meta_table_data, colWidths=[80, 180, 80, 180])
        meta_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("SPAN", (1, 3), (3, 3)),
        ]))
        ep_elements.append(meta_table)
        ep_elements.append(Spacer(1, 4))

        # Synopsis
        ep_elements.append(Paragraph(f"<b>Synopsis:</b> {synopsis}", body_style))
        ep_elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceBefore=4, spaceAfter=8))

        story.append(KeepTogether(ep_elements))

    doc.build(story)
    logger.info(f"Successfully generated PDF lore book: {output_pdf_path} ({output_pdf_path.stat().st_size} bytes)")


async def ingest_episodes_and_events_to_mongo(series_data: dict):
    """
    Upserts extracted episode records into db['episodes'] and calendar events into db['events'].
    Also ensures parent anime records exist in db['anime'].
    """
    logger.info("=" * 80)
    logger.info("UPSERTING ANIME EPISODES AND CONNECTING TO TODAY'S EVENTS")
    logger.info("=" * 80)

    await connect_db()
    db = get_db()

    total_episodes_upserted = 0
    total_events_upserted = 0

    for cfg in SERIES_CONFIG:
        slug = cfg["slug"]
        anime_id = cfg["anime_id"]
        title = cfg["title"]
        episodes = series_data.get(slug, [])

        if not episodes:
            continue

        # 1. Upsert parent anime record in db['anime']
        await db["anime"].update_one(
            {"_id": anime_id},
            {
                "$setOnInsert": {
                    "_id": anime_id,
                    "title": {
                        "english": title,
                        "romaji": cfg["romaji"],
                        "japanese": cfg["japanese"],
                    },
                    "slug": slug,
                    "type": "TV",
                    "status": "FINISHED",
                    "episodes": len(episodes),
                    "created_at": datetime.now(timezone.utc),
                    "is_deleted": False,
                }
            },
            upsert=True,
        )

        episode_ops = []
        event_ops = []

        for ep in episodes:
            ep_num = ep["episode_number"]
            ep_id = ep["_id"]
            ep_title = ep["title"]
            rel_date = ep["release_date"]
            parsed_date = parse_date(rel_date)
            normalized_date = parsed_date[0] if parsed_date else rel_date

            ep_doc = {
                "anime_id": anime_id,
                "series_id": anime_id,
                "anime_title": title,
                "episode_number": ep_num,
                "title": ep_title,
                "kanji_title": ep.get("kanji_title") or "",
                "romaji_title": ep.get("romaji_title") or "",
                "release_date": normalized_date,
                "english_airdate": ep.get("english_airdate") or "",
                "director": ep.get("director") or "",
                "arc": ep.get("arc") or "",
                "is_filler": ep.get("is_filler", False),
                "canon_type": ep.get("canon_type", "manga canon"),
                "manga_chapters_covered": ep.get("manga_chapters_covered") or "",
                "manga_chapters": ep.get("manga_chapters") or [],
                "summary": ep.get("summary") or "",
                "characters_appeared": ep.get("characters_appeared") or [],
                "character_ids": ep.get("character_ids") or [],
                "is_deleted": False,
                "deleted_at": None,
                "updated_at": datetime.now(timezone.utc),
            }

            episode_ops.append(
                UpdateOne(
                    {"anime_id": anime_id, "episode_number": ep_num},
                    {"$set": ep_doc, "$setOnInsert": {"_id": ep_id}},
                    upsert=True,
                )
            )

            # 2. Upsert calendar event record in db['events']
            if parsed_date:
                iso_date, year, month, day = parsed_date
                event_id = f"event_{ep_id}"

                canon_label = "Filler" if ep.get("is_filler") else "Manga Canon"
                chars_preview = ", ".join(ep.get("characters_appeared", [])[:3])
                feat_str = f" Features {chars_preview}." if chars_preview else ""
                desc = (
                    f"{title} Episode {ep_num}: '{ep_title}' was originally broadcast in Japan on this day in {year} ({canon_status_text(ep)}).{feat_str}"
                )

                event_doc = {
                    "title": f"{title} Episode {ep_num} Aired",
                    "description": desc,
                    "month": month,
                    "day": day,
                    "year": year,
                    "event_type": "anime_release",
                    "anime_id": anime_id,
                    "episode_id": ep_id,
                    "episode_number": ep_num,
                    "episode_title": ep_title,
                    "is_filler": ep.get("is_filler", False),
                    "manga_chapters_covered": ep.get("manga_chapters_covered") or "",
                    "character_ids": ep.get("character_ids") or [],
                    "release_date": iso_date,
                    "summary": (ep.get("summary") or "")[:500],
                    "tags": [slug, "anime", f"episode_{ep_num}", canon_label.lower()],
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

        # Bulk write episodes
        if episode_ops:
            batch_size = 500
            for i in range(0, len(episode_ops), batch_size):
                chunk = episode_ops[i:i + batch_size]
                res = await db["episodes"].bulk_write(chunk, ordered=False)
                total_episodes_upserted += (res.upserted_count + res.modified_count)

        # Bulk write events
        if event_ops:
            batch_size = 500
            for i in range(0, len(event_ops), batch_size):
                chunk = event_ops[i:i + batch_size]
                res = await db["events"].bulk_write(chunk, ordered=False)
                total_events_upserted += (res.upserted_count + res.modified_count)

        logger.info(f"[{title}] Synced {len(episode_ops)} episodes and {len(event_ops)} calendar events.")

    logger.info("=" * 80)
    logger.info(f"TOTAL EPISODES UPSERTED/MODIFIED: {total_episodes_upserted}")
    logger.info(f"TOTAL CALENDAR EVENTS UPSERTED/MODIFIED: {total_events_upserted}")
    logger.info("=" * 80)


def canon_status_text(ep: dict) -> str:
    if ep.get("is_filler"):
        return "Anime-Original Filler"
    cov = ep.get("manga_chapters_covered")
    return f"Canon, adapts Manga Chapter {cov}" if cov else "Manga Canon"


async def train_rag_vectors_from_pdfs(pdf_map: dict[str, Path]):
    """
    Ingests each generated episode PDF through lore_service.process_lore_pdf,
    generating 384-dimensional dense vectors with all-MiniLM-L6-v2, and stores them in db['lore_chunks'].
    """
    logger.info("=" * 80)
    logger.info("TRAINING RAG MODEL (VECTOR EMBEDDING & CHUNK INGESTION)")
    logger.info("=" * 80)

    await connect_db()

    for series_id, pdf_path in pdf_map.items():
        if not pdf_path.exists():
            logger.warning(f"PDF not found for {series_id}: {pdf_path}")
            continue

        logger.info(f"[{series_id}] Reading PDF: {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        logger.info(f"[{series_id}] Generating semantic text chunks and dense vector embeddings...")
        chunks = lore_service.process_lore_pdf(
            file_bytes=pdf_bytes,
            series_id=series_id,
            character_ids=None,
            source_file=pdf_path.name,
        )
        logger.info(f"[{series_id}] Created {len(chunks)} embedded vector chunks.")

        # Insert chunks into lore_chunks collection
        deleted = await lore_repository.delete_by_series(series_id)
        if deleted > 0:
            logger.info(f"[{series_id}] Cleared {deleted} previous chunks.")

        await lore_repository.insert_chunks(chunks)
        logger.info(f"[{series_id}] Successfully ingested {len(chunks)} chunks into 'lore_chunks' collection!")

    logger.info("=" * 80)
    logger.info("RAG VECTOR INGESTION COMPLETE FOR ALL ANIME EPISODES")
    logger.info("=" * 80)


async def main():
    data_dir = PROJECT_ROOT / "data" / "anime_episodes"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Scrape episodes
    series_data = scrape_all_episodes(data_dir)

    # 2. Generate PDF lore books
    pdf_map = {}
    for cfg in SERIES_CONFIG:
        slug = cfg["slug"]
        anime_id = cfg["anime_id"]
        episodes = series_data.get(slug, [])
        pdf_path = data_dir / f"{slug}_episodes_lore.pdf"
        generate_episode_lore_pdf(cfg["title"], episodes, pdf_path)
        pdf_map[anime_id] = pdf_path

    # 3. Store into MongoDB episodes & events collections
    await ingest_episodes_and_events_to_mongo(series_data)

    # 4. Train RAG vector search model (embed into lore_chunks)
    await train_rag_vectors_from_pdfs(pdf_map)

    await close_db()
    logger.info("ALL PIPELINE TASKS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
