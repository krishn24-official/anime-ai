import argparse
import asyncio
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate

# Project root path setup
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.utils.slug import create_slug  # noqa: E402
from app.db.mongo import close_db, connect_db, get_db  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("one_piece_chapter_scraper")

FANDOM_API_URL = "https://onepiece.fandom.com/api.php"
USER_AGENT = "AnimeAI-Bot/1.0 (entertainment aggregator; python-urllib)"


def clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not text:
        return ""
    # Replace line-breaks and paragraph breaks with spaces
    text = re.sub(r"<(?:br|p|/p)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Strip all remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse multiple whitespaces per line
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def clean_text_for_pdf(text: str) -> str:
    """Replace non-Latin1 / unsupported Unicode characters for ReportLab standard fonts."""
    if not text:
        return ""
    replacements = {
        "\u2014": " - ",
        "\u2013": " - ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\uff08": "(",
        "\uff09": ")",
        "\u014d": "o",
        "\u014c": "O",
        "\u016b": "u",
        "\u016a": "U",
        "\u0101": "a",
        "\u0100": "A",
        "\u012b": "i",
        "\u012a": "I",
        "\u0113": "e",
        "\u0112": "E",
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # Keep only ASCII printable characters to prevent PDF font encoding issues
    return "".join(c if ord(c) < 128 else "" for c in text)


def fetch_chapter_from_fandom(chapter_number: int, retries: int = 3) -> dict[str, Any] | None:
    """Fetch structured metadata and summaries for a specific One Piece chapter from Fandom API."""
    url = f"{FANDOM_API_URL}?action=parse&page=Chapter_{chapter_number}&format=json"
    headers = {"User-Agent": USER_AGENT}

    req = urllib.request.Request(url, headers=headers)
    data = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except Exception as e:
            if attempt < retries:
                time.sleep(1.2 * attempt)
            else:
                logger.error(f"Error fetching Chapter {chapter_number} after {retries} attempts: {e}")
                return None

    if "error" in data:
        logger.warning(
            f"Fandom API error for Chapter {chapter_number}: {data['error'].get('info')}"
        )
        return None

    parse_data = data.get("parse", {})
    html = parse_data.get("text", {}).get("*", "")
    page_title = parse_data.get("title", f"Chapter {chapter_number}")

    # 1. Parse Portable Infobox fields
    infobox_items = re.findall(
        r'data-source="([^"]+)"[^>]*>(.*?)</div>', html, re.DOTALL
    )
    metadata = {}
    for key, raw_val in infobox_items:
        clean_val = clean_html(raw_val)
        clean_val = " ".join(clean_val.split())
        metadata[key] = clean_val

    # Title resolution
    english_title = metadata.get("ename") or metadata.get("title") or page_title
    english_title = re.sub(
        r"Chapter\s+Info\s+Volume:.*", "", english_title, flags=re.IGNORECASE
    ).strip()
    english_title = re.sub(
        r"^(?:Viz\s+Title|Title):\s*", "", english_title, flags=re.IGNORECASE
    ).strip()

    # Clean date and issue
    release_date = metadata.get("date2", "")
    release_date = re.sub(
        r"^(?:Release\s+Date|Date):\s*", "", release_date, flags=re.IGNORECASE
    )
    release_date = re.sub(r"\[ref\]|\[\d+\]", "", release_date).strip()

    wsj_issue = re.sub(
        r"^WSJ\s+Issue:\s*", "", metadata.get("jump", ""), flags=re.IGNORECASE
    ).strip()
    japanese_title = re.sub(
        r"^Japanese\s+Title:\s*", "", metadata.get("jname", ""), flags=re.IGNORECASE
    ).strip()
    romanized_title = re.sub(
        r"^Romanized\s+Title:\s*", "", metadata.get("rname", ""), flags=re.IGNORECASE
    ).strip()
    anime_adaptation = re.sub(
        r"^Anime:\s*", "", metadata.get("anime", ""), flags=re.IGNORECASE
    ).strip()

    # 2. Extract Characters Appeared
    characters = []
    char_match = re.search(
        r'id="Characters".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if char_match:
        raw_chars = char_match.group(1)
        found_links = re.findall(
            r'<a\s+[^>]*title="([^"]+)"[^>]*>([^<]+)</a>', raw_chars
        )
        seen = set()
        for wiki_page, char_name in found_links:
            char_name = char_name.strip()
            wiki_page = wiki_page.strip()
            if (
                wiki_page not in seen
                and char_name
                and not any(
                    skip in wiki_page.lower()
                    for skip in [
                        "category:",
                        "file:",
                        "template:",
                        "help:",
                        "animal species",
                        "pirate",
                    ]
                )
            ):
                seen.add(wiki_page)
                characters.append(
                    {
                        "name": char_name,
                        "wiki_page": wiki_page,
                        "slug": f"char_{create_slug(char_name)}",
                    }
                )

    # 3. Extract Short Summary
    short_summary = ""
    sum_match = re.search(
        r'id="Short_Summary".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if sum_match:
        short_summary = clean_html(sum_match.group(1))

    # 4. Extract Long Summary
    long_summary = ""
    long_sum_match = re.search(
        r'id="Long_Summary".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if long_sum_match:
        long_summary = clean_html(long_sum_match.group(1))

    # Prefer long summary if available, fallback to short summary
    full_narrative = long_summary or short_summary

    # Extract Volume number
    volume_str = metadata.get("volume") or ""
    volume_num = None
    vol_digits = re.search(r"\d+", volume_str)
    if vol_digits:
        volume_num = int(vol_digits.group(0))

    # Extract Page count
    page_count = None
    pages_match = re.search(r"\d+", metadata.get("page") or "")
    if pages_match:
        page_count = int(pages_match.group(0))

    character_ids = [c["slug"] for c in characters]

    return {
        "_id": f"chapter_one_piece_{chapter_number}",
        "manga_id": "manga_one_piece",
        "series_id": "manga_one_piece",
        "series_title": "One Piece",
        "chapter_number": chapter_number,
        "title": english_title,
        "japanese_title": japanese_title,
        "romanized_title": romanized_title,
        "volume": volume_num,
        "pages": page_count,
        "release_date": release_date,
        "wsj_issue": wsj_issue,
        "anime_adaptation": anime_adaptation,
        "short_summary": short_summary,
        "long_summary": long_summary,
        "summary": full_narrative,
        "characters_appeared": characters,
        "character_ids": character_ids,
        "source_url": f"https://onepiece.fandom.com/wiki/Chapter_{chapter_number}",
        "scraped_at": datetime.now(timezone.utc),
    }


def generate_markdown_doc(chapters: list[dict], output_file: Path) -> str:
    """Generate a clean Markdown document formatted for RAG ingestion."""
    lines = [
        "# One Piece Canon Chapter Lore and Story Knowledge",
        "",
        "> Official chapter guide, lore synopsis, and character appearances from Eiichiro Oda's One Piece manga.",
        "",
        "---",
        "",
    ]

    for ch in sorted(chapters, key=lambda x: x["chapter_number"]):
        ch_num = ch["chapter_number"]
        title = ch.get("title", f"Chapter {ch_num}")
        lines.append(f"## Chapter {ch_num}: {title}")
        lines.append("")

        meta_parts = []
        if ch.get("volume"):
            meta_parts.append(f"**Volume**: {ch['volume']}")
        if ch.get("pages"):
            meta_parts.append(f"**Pages**: {ch['pages']}")
        if ch.get("release_date"):
            meta_parts.append(f"**Release Date**: {ch['release_date']}")
        if ch.get("wsj_issue"):
            meta_parts.append(f"**Jump Issue**: {ch['wsj_issue']}")

        if meta_parts:
            lines.append(" • ".join(meta_parts))
            lines.append("")

        if ch.get("anime_adaptation"):
            lines.append(f"**Anime Adaptation**: {ch['anime_adaptation']}")
            lines.append("")

        chars = ch.get("characters_appeared", [])
        if chars:
            char_names = [c["name"] for c in chars]
            lines.append(f"### Characters in Chapter {ch_num}")
            lines.append(", ".join(char_names))
            lines.append("")

        lines.append("### Story Events & Summary")
        summary_text = (
            ch.get("long_summary")
            or ch.get("short_summary")
            or "No synopsis available."
        )
        lines.append(summary_text)
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(
        f"Saved Markdown RAG lore document to: {output_file} ({len(content)} chars)"
    )
    return content


def generate_pdf_doc(chapters: list[dict], output_file: Path) -> Path:
    """Generate a high-density, multi-page PDF suitable for RAG embedding and download."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_file),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1A202C"),
        spaceAfter=8,
    )
    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=15,
    )
    ch_heading_style = ParagraphStyle(
        "ChapterHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=12,
        spaceAfter=4,
        keepWithNext=True,
    )
    meta_style = ParagraphStyle(
        "MetaText",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#718096"),
        spaceAfter=6,
        keepWithNext=True,
    )
    char_heading_style = ParagraphStyle(
        "CharHeading",
        parent=styles["Heading4"],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#2D3748"),
        spaceBefore=4,
        spaceAfter=2,
        keepWithNext=True,
    )
    char_list_style = ParagraphStyle(
        "CharList",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=6,
    )
    summary_body_style = ParagraphStyle(
        "SummaryBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1A202C"),
        spaceAfter=8,
    )

    story = [
        Paragraph("One Piece Manga Chapter Canon & Lore", title_style),
        Paragraph(
            f"Generated Lore Knowledge Document for AI Chatbot RAG | Compiled {datetime.now(timezone.utc).strftime('%B %Y')}",
            subtitle_style,
        ),
        HRFlowable(
            width="100%", thickness=1.5, color=colors.HexColor("#CBD5E0"), spaceAfter=12
        ),
    ]

    for ch in sorted(chapters, key=lambda x: x["chapter_number"]):
        ch_num = ch["chapter_number"]
        title_raw = clean_text_for_pdf(ch.get("title", f"Chapter {ch_num}"))

        # Meta info
        meta_items = [f"<b>Chapter</b>: {ch_num}"]
        if ch.get("volume"):
            meta_items.append(f"<b>Volume</b>: {ch['volume']}")
        if ch.get("release_date"):
            meta_items.append(
                f"<b>Released</b>: {clean_text_for_pdf(ch['release_date'])}"
            )
        if ch.get("wsj_issue"):
            meta_items.append(f"<b>Issue</b>: {clean_text_for_pdf(ch['wsj_issue'])}")

        meta_line = " &nbsp;|&nbsp; ".join(meta_items)

        story.append(Paragraph(f"Chapter {ch_num}: {title_raw}", ch_heading_style))
        story.append(Paragraph(meta_line, meta_style))

        # Characters
        chars = ch.get("characters_appeared", [])
        if chars:
            c_names = [clean_text_for_pdf(c["name"]) for c in chars[:25]]
            char_str = ", ".join(c_names)
            if len(chars) > 25:
                char_str += f" and {len(chars) - 25} more"
            story.append(Paragraph("<b>Characters Appeared:</b>", char_heading_style))
            story.append(Paragraph(char_str, char_list_style))

        # Summary
        summary_raw = ch.get("long_summary") or ch.get("short_summary") or ""
        clean_sum = clean_text_for_pdf(summary_raw)
        if clean_sum:
            # Split summary into paragraphs
            for p in clean_sum.split("\n"):
                p = p.strip()
                if p:
                    story.append(Paragraph(p, summary_body_style))

        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#E2E8F0"),
                spaceBefore=6,
                spaceAfter=8,
            )
        )

    doc.build(story)
    logger.info(
        f"Saved PDF document to: {output_file} ({output_file.stat().st_size} bytes)"
    )
    return output_file


async def save_chapters_to_db(chapters: list[dict]) -> int:
    """Upsert chapters into MongoDB Atlas collection 'chapters' and ensure 'manga' parent record."""
    await connect_db()
    db = get_db()

    # 1. Ensure manga_one_piece parent entry exists in 'manga' collection
    await db["manga"].update_one(
        {"_id": "manga_one_piece"},
        {
            "$setOnInsert": {
                "_id": "manga_one_piece",
                "name": "One Piece",
                "title": {"english": "One Piece", "romaji": "ONE PIECE"},
                "author": "Eiichiro Oda",
                "status": "RELEASING",
                "type": "MANGA",
                "synopsis": "Monkey D. Luffy embarks on a quest to find the legendary treasure, the One Piece, and become the Pirate King.",
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    # 2. Upsert each chapter into 'chapters' collection
    saved_count = 0
    for ch in chapters:
        await db["chapters"].update_one(
            {"manga_id": ch["manga_id"], "chapter_number": ch["chapter_number"]},
            {"$set": ch},
            upsert=True,
        )
        saved_count += 1

    await close_db()
    logger.info(
        f"Upserted {saved_count} chapters into MongoDB Atlas collection 'chapters'"
    )
    return saved_count


async def ingest_into_rag_lore(
    pdf_path: Path, series_id: str = "manga_one_piece"
) -> int:
    """Directly ingest the generated chapter PDF into the chatbot's lore_chunks collection."""
    from app.services import lore_service

    if not pdf_path.exists():
        logger.error(f"Cannot ingest: PDF {pdf_path} does not exist.")
        return 0

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    logger.info(
        f"Starting RAG embedding ingestion for {pdf_path.name} ({len(file_bytes)} bytes)..."
    )
    result = await lore_service.process_lore_pdf(
        file_bytes=file_bytes,
        filename=pdf_path.name,
        series_id=series_id,
        character_ids=["char_monkey_d_luffy", "char_shanks", "char_roronoa_zoro"],
    )

    logger.info(
        f"RAG Ingestion Complete! Chunks created: {result.chunks_created}, Status: {result.status}"
    )
    return result.chunks_created


async def main():
    parser = argparse.ArgumentParser(
        description="Scrape One Piece manga chapters from Fandom API, store in MongoDB Atlas, and build RAG lore documents."
    )
    parser.add_argument(
        "--start", type=int, default=1, help="Starting chapter number (default: 1)"
    )
    parser.add_argument(
        "--end",
        type=int,
        default=5,
        help="Ending chapter number (inclusive, default: 5 for testing)",
    )
    parser.add_argument(
        "--chapters",
        type=str,
        default="",
        help="Comma-separated specific chapters to fetch (e.g. '1,2,3,1000')",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.4,
        help="Polite delay between API requests in seconds (default: 0.4)",
    )
    parser.add_argument(
        "--no-db", action="store_true", help="Skip saving to MongoDB Atlas"
    )
    parser.add_argument(
        "--ingest-rag",
        action="store_true",
        help="Directly embed and ingest into lore_chunks for chatbot RAG",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/manga_chapters",
        help="Output directory for generated PDF and Markdown files",
    )

    args = parser.parse_args()

    # Determine chapter list
    if args.chapters:
        chapter_nums = [
            int(c.strip()) for c in args.chapters.split(",") if c.strip().isdigit()
        ]
    else:
        chapter_nums = list(range(args.start, args.end + 1))

    logger.info(
        f"Fetching {len(chapter_nums)} chapters from Fandom (Chapters: {chapter_nums[0]} to {chapter_nums[-1]})..."
    )

    scraped_chapters = []
    for idx, num in enumerate(chapter_nums):
        logger.info(f"[{idx+1}/{len(chapter_nums)}] Scraping Chapter {num}...")
        ch_data = fetch_chapter_from_fandom(num)
        if ch_data:
            scraped_chapters.append(ch_data)
            logger.info(
                f"  -> OK: '{ch_data['title']}' ({len(ch_data.get('characters_appeared', []))} characters, summary {len(ch_data.get('summary', ''))} chars)"
            )
        else:
            logger.warning(f"  -> FAILED / SKIPPED Chapter {num}")
        time.sleep(args.delay)

    if not scraped_chapters:
        logger.error("No chapters scraped successfully. Exiting.")
        return

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save JSON dump
    json_path = out_dir / "one_piece_chapters.json"
    with open(json_path, "w", encoding="utf-8") as f:
        # Convert non-serializable objects (datetime)
        serializable = []
        for c in scraped_chapters:
            item = dict(c)
            if isinstance(item.get("scraped_at"), datetime):
                item["scraped_at"] = item["scraped_at"].isoformat()
            serializable.append(item)
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved JSON export to: {json_path}")

    # 2. Save Markdown RAG Document
    md_path = out_dir / "one_piece_chapters_lore.md"
    generate_markdown_doc(scraped_chapters, md_path)

    # 3. Save PDF RAG Document
    pdf_path = out_dir / "one_piece_chapters_lore.pdf"
    generate_pdf_doc(scraped_chapters, pdf_path)

    # 4. Save to MongoDB Atlas
    if not args.no_db:
        await save_chapters_to_db(scraped_chapters)

    # 5. Optional Direct RAG Ingestion
    if getattr(args, "ingest_rag", False):
        await ingest_into_rag_lore(pdf_path, series_id="manga_one_piece")

    print("\n" + "=" * 60)
    print("FINISHED SUCCESSFULLY!")
    print(f"Total Chapters Processed: {len(scraped_chapters)}")
    print(f"Markdown Lore Document : {md_path}")
    print(f"PDF Lore Document      : {pdf_path}")
    print(f"JSON Export            : {json_path}")
    if not args.no_db:
        print("MongoDB Atlas          : Successfully updated 'chapters' collection")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
