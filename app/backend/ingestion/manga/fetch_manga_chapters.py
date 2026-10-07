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

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate

    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# Project root path setup
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.utils.slug import create_slug  # noqa: E402
from app.db.mongo import close_db, connect_db, get_db  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("manga_chapter_scraper")

USER_AGENT = "AnimeAI-Bot/1.0 (entertainment aggregator; python-urllib)"

# Supported manga configurations
MANGA_CONFIGS = {
    "one_piece": {
        "manga_id": "manga_one_piece",
        "title": "One Piece",
        "author": "Eiichiro Oda",
        "domain": "onepiece.fandom.com",
        "total_chapters": 1194,
        "aliases": ["onepiece", "op"],
        "pdf_name": "one_piece_chapters_lore.pdf",
        "md_name": "one_piece_chapters_lore.md",
        "json_name": "one_piece_chapters.json",
    },
    "naruto": {
        "manga_id": "manga_naruto",
        "title": "Naruto",
        "author": "Masashi Kishimoto",
        "domain": "naruto.fandom.com",
        "total_chapters": 700,
        "aliases": ["naruto_shippuden"],
        "pdf_name": "naruto_chapters_lore.pdf",
        "md_name": "naruto_chapters_lore.md",
        "json_name": "naruto_chapters.json",
    },
    "bleach": {
        "manga_id": "manga_bleach",
        "title": "Bleach",
        "author": "Tite Kubo",
        "domain": "bleach.fandom.com",
        "total_chapters": 686,
        "aliases": [],
        "pdf_name": "bleach_chapters_lore.pdf",
        "md_name": "bleach_chapters_lore.md",
        "json_name": "bleach_chapters.json",
    },
    "attack_on_titan": {
        "manga_id": "manga_attack_on_titan",
        "title": "Attack on Titan",
        "author": "Hajime Isayama",
        "domain": "attackontitan.fandom.com",
        "total_chapters": 139,
        "aliases": ["aot", "shingeki_no_kyojin", "snk"],
        "pdf_name": "attack_on_titan_chapters_lore.pdf",
        "md_name": "attack_on_titan_chapters_lore.md",
        "json_name": "attack_on_titan_chapters.json",
    },
    "dragon_ball": {
        "manga_id": "manga_dragon_ball",
        "title": "Dragon Ball",
        "author": "Akira Toriyama",
        "domain": "dragonball.fandom.com",
        "total_chapters": 519,
        "aliases": ["dbz", "dragonball"],
        "pdf_name": "dragon_ball_chapters_lore.pdf",
        "md_name": "dragon_ball_chapters_lore.md",
        "json_name": "dragon_ball_chapters.json",
    },
}


def resolve_manga_key(user_input: str) -> str:
    """Normalize user input to supported manga configuration key."""
    norm = user_input.strip().lower().replace("-", "_").replace(" ", "_")
    if norm in MANGA_CONFIGS:
        return norm
    for key, cfg in MANGA_CONFIGS.items():
        if norm in cfg["aliases"]:
            return key
    raise ValueError(
        f"Unsupported manga '{user_input}'. Available: {list(MANGA_CONFIGS.keys())}"
    )


def clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not text:
        return ""
    text = re.sub(r"<(?:br|p|/p)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
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
    return "".join(c if ord(c) < 128 else "" for c in text)


def api_request(url: str, retries: int = 3, timeout: int = 20) -> dict | None:
    """Perform robust HTTP GET request to Fandom MediaWiki API with exponential backoff."""
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < retries:
                time.sleep(1.2 * attempt)
            else:
                logger.error(f"HTTP request failed for {url}: {e}")
                return None
    return None


def extract_characters_from_html(html_snippet: str) -> list[dict]:
    """Extract character links from an HTML snippet."""
    characters = []
    found_links = re.findall(
        r'<a\s+[^>]*title="([^"]+)"[^>]*>([^<]+)</a>', html_snippet
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
                    "chapter",
                    "volume",
                    "episode",
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
    return characters


# ── Individual Franchise Scrapers ─────────────────────────────────────────────


def scrape_one_piece_chapter(num: int) -> dict[str, Any] | None:
    """Scrape a One Piece chapter."""
    url = f"https://onepiece.fandom.com/api.php?action=parse&page=Chapter_{num}&format=json"
    data = api_request(url)
    if not data or "parse" not in data:
        return None

    parse_data = data["parse"]
    html = parse_data.get("text", {}).get("*", "")
    page_title = parse_data.get("title", f"Chapter {num}")

    # Infobox fields
    infobox_items = re.findall(
        r'data-source="([^"]+)"[^>]*>(.*?)</div>', html, re.DOTALL
    )
    meta = {k: " ".join(clean_html(v).split()) for k, v in infobox_items}

    english_title = meta.get("ename") or meta.get("title") or page_title
    english_title = re.sub(
        r"Chapter\s+Info\s+Volume:.*", "", english_title, flags=re.IGNORECASE
    ).strip()
    english_title = re.sub(
        r"^(?:Viz\s+Title|Title):\s*", "", english_title, flags=re.IGNORECASE
    ).strip()

    release_date = meta.get("date2", "")
    release_date = re.sub(
        r"^(?:Release\s+Date|Date):\s*", "", release_date, flags=re.IGNORECASE
    )
    release_date = re.sub(r"\[ref\]|\[\d+\]", "", release_date).strip()

    # Characters
    char_match = re.search(
        r'id="Characters".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    characters = extract_characters_from_html(char_match.group(1)) if char_match else []

    # Summaries
    short_sum = ""
    short_match = re.search(
        r'id="Short_Summary".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if short_match:
        short_sum = clean_html(short_match.group(1))

    long_sum = ""
    long_match = re.search(
        r'id="Long_Summary".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if long_match:
        long_sum = clean_html(long_match.group(1))

    full_narrative = long_sum or short_sum

    # Volume & Pages
    vol_digits = re.search(r"\d+", meta.get("volume") or "")
    volume_num = int(vol_digits.group(0)) if vol_digits else None
    pages_digits = re.search(r"\d+", meta.get("page") or "")
    page_count = int(pages_digits.group(0)) if pages_digits else None

    return {
        "_id": f"chapter_one_piece_{num}",
        "manga_id": "manga_one_piece",
        "series_id": "manga_one_piece",
        "series_title": "One Piece",
        "chapter_number": num,
        "title": english_title,
        "volume": volume_num,
        "pages": page_count,
        "release_date": release_date,
        "summary": full_narrative,
        "short_summary": short_sum,
        "long_summary": long_sum,
        "characters_appeared": characters,
        "character_ids": [c["slug"] for c in characters],
        "source_url": f"https://onepiece.fandom.com/wiki/Chapter_{num}",
        "scraped_at": datetime.now(timezone.utc),
    }


def scrape_naruto_chapter(num: int) -> dict[str, Any] | None:
    """Scrape a Naruto chapter using MediaNav template resolution."""
    # 1. Resolve chapter page name via MediaNav template
    t_url = f"https://naruto.fandom.com/api.php?action=expandtemplates&text={{{{MediaNav|Chapter|{num}}}}}&prop=wikitext&format=json"
    t_data = api_request(t_url)
    if not t_data or "expandtemplates" not in t_data:
        return None

    wt = t_data["expandtemplates"].get("wikitext", "")
    target_match = re.search(
        r"\[\[(?:SMW::off\]\]\[\[)?([^|\]]+)(?:\|[^\]]+)?(?:\]\]\[\[SMW::on)?\]\]", wt
    )
    page_title = target_match.group(1).strip() if target_match else f"Chapter_{num}"

    # 2. Parse the chapter page
    p_url = f"https://naruto.fandom.com/api.php?action=parse&page={urllib.parse.quote(page_title)}&prop=text|wikitext&format=json"
    p_data = api_request(p_url)
    if not p_data or "parse" not in p_data:
        return None

    parse_data = p_data["parse"]
    html = parse_data.get("text", {}).get("*", "")
    raw_wt = parse_data.get("wikitext", {}).get("*", "")

    # Clean title
    english_title = page_title.split("(")[0].strip()
    title_match = re.search(r"\|\s*english\s*=\s*([^|\n]+)", raw_wt)
    if title_match:
        english_title = title_match.group(1).strip()

    # Volume & Release date
    vol_match = re.search(r"\|\s*volume\s*=\s*(\d+)", raw_wt)
    volume_num = int(vol_match.group(1)) if vol_match else None

    date_match = re.search(r"\|\s*japanese release date\s*=\s*([^|\n]+)", raw_wt)
    release_date = date_match.group(1).strip() if date_match else ""

    # Arc
    arc_match = re.search(r"\|\s*arc\s*=\s*([^|\n]+)", raw_wt)
    arc_name = arc_match.group(1).strip() if arc_match else ""

    # Summary
    sum_match = re.search(
        r'id="Summary".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    summary_text = clean_html(sum_match.group(1)) if sum_match else ""

    # Characters from summary links
    characters = extract_characters_from_html(sum_match.group(1)) if sum_match else []

    return {
        "_id": f"chapter_naruto_{num}",
        "manga_id": "manga_naruto",
        "series_id": "manga_naruto",
        "series_title": "Naruto",
        "chapter_number": num,
        "title": english_title,
        "volume": volume_num,
        "arc": arc_name,
        "release_date": release_date,
        "summary": summary_text,
        "characters_appeared": characters,
        "character_ids": [c["slug"] for c in characters],
        "source_url": f"https://naruto.fandom.com/wiki/{urllib.parse.quote(page_title)}",
        "scraped_at": datetime.now(timezone.utc),
    }


def scrape_aot_chapter(num: int) -> dict[str, Any] | None:
    """Scrape an Attack on Titan chapter."""
    url = f"https://attackontitan.fandom.com/api.php?action=parse&page=Chapter_{num}&redirects=1&format=json"
    data = api_request(url)
    if not data or "parse" not in data:
        return None

    parse_data = data["parse"]
    html = parse_data.get("text", {}).get("*", "")
    page_title = parse_data.get("title", f"Chapter {num}")
    english_title = re.sub(r"\(Chapter(?:\s+\d+)?\)", "", page_title).strip()

    # Infobox fields
    infobox_items = re.findall(
        r'data-source="([^"]+)"[^>]*>(.*?)</div>', html, re.DOTALL
    )
    meta = {k: " ".join(clean_html(v).split()) for k, v in infobox_items}

    vol_digits = re.search(r"\d+", meta.get("volume") or "")
    volume_num = int(vol_digits.group(0)) if vol_digits else None
    release_date = meta.get("release_date") or meta.get("date") or ""

    # Summary
    sum_match = re.search(
        r'id="Summary".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    summary_text = clean_html(sum_match.group(1)) if sum_match else ""

    # Characters
    char_match = re.search(
        r'id="Characters[^"]*".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    characters = extract_characters_from_html(char_match.group(1)) if char_match else []

    return {
        "_id": f"chapter_attack_on_titan_{num}",
        "manga_id": "manga_attack_on_titan",
        "series_id": "manga_attack_on_titan",
        "series_title": "Attack on Titan",
        "chapter_number": num,
        "title": english_title,
        "volume": volume_num,
        "release_date": release_date,
        "summary": summary_text,
        "characters_appeared": characters,
        "character_ids": [c["slug"] for c in characters],
        "source_url": f"https://attackontitan.fandom.com/wiki/Chapter_{num}",
        "scraped_at": datetime.now(timezone.utc),
    }


def scrape_dragon_ball_chapter(num: int) -> dict[str, Any] | None:
    """Scrape a Dragon Ball chapter."""
    url = f"https://dragonball.fandom.com/api.php?action=parse&page=Chapter_{num}&redirects=1&format=json"
    data = api_request(url)
    if not data or "parse" not in data:
        return None

    parse_data = data["parse"]
    html = parse_data.get("text", {}).get("*", "")
    page_title = parse_data.get("title", f"Chapter {num}")

    infobox_items = re.findall(
        r'data-source="([^"]+)"[^>]*>(.*?)</div>', html, re.DOTALL
    )
    meta = {k: " ".join(clean_html(v).split()) for k, v in infobox_items}

    vol_digits = re.search(r"\d+", meta.get("volume") or "")
    volume_num = int(vol_digits.group(0)) if vol_digits else None
    release_date = meta.get("release_date") or meta.get("date") or ""

    # Summary
    sum_match = re.search(
        r'id="Summary".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    summary_text = clean_html(sum_match.group(1)) if sum_match else ""

    # Characters
    char_match = re.search(
        r'id="Characters".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    characters = extract_characters_from_html(char_match.group(1)) if char_match else []

    return {
        "_id": f"chapter_dragon_ball_{num}",
        "manga_id": "manga_dragon_ball",
        "series_id": "manga_dragon_ball",
        "series_title": "Dragon Ball",
        "chapter_number": num,
        "title": page_title,
        "volume": volume_num,
        "release_date": release_date,
        "summary": summary_text,
        "characters_appeared": characters,
        "character_ids": [c["slug"] for c in characters],
        "source_url": f"https://dragonball.fandom.com/wiki/Chapter_{num}",
        "scraped_at": datetime.now(timezone.utc),
    }


def scrape_bleach_chapter(num: int) -> dict[str, Any] | None:
    """Scrape a Bleach chapter using Chapter redirect to Volume or standalone page."""
    # Try Chapter redirect first
    url = f"https://bleach.fandom.com/api.php?action=parse&page=Chapter_{num}&redirects=1&prop=text|wikitext&format=json"
    data = api_request(url)
    if not data or "parse" not in data:
        # Fallback to 3-digit prefix search
        prefix = f"{num:03d}."
        p_url = f"https://bleach.fandom.com/api.php?action=query&list=allpages&apprefix={prefix}&aplimit=1&format=json"
        p_data = api_request(p_url)
        pages = p_data.get("query", {}).get("allpages", []) if p_data else []
        if pages:
            title = pages[0]["title"]
            url = f"https://bleach.fandom.com/api.php?action=parse&page={urllib.parse.quote(title)}&redirects=1&prop=text|wikitext&format=json"
            data = api_request(url)

    if not data or "parse" not in data:
        return None

    parse_data = data["parse"]
    html = parse_data.get("text", {}).get("*", "")
    page_title = parse_data.get("title", f"Chapter {num}")

    # If it resolved to a Volume page, extract chapter section from volume
    target_pattern = (
        rf'(?:id="0*{num}\.[^"]*".*?</h\d>)(.*?)(?:<h[23]|<div class="navbox")'
    )
    ch_sec_match = re.search(target_pattern, html, re.DOTALL | re.IGNORECASE)

    if ch_sec_match:
        sec_html = ch_sec_match.group(1)
        summary_text = clean_html(sec_html)
        characters = extract_characters_from_html(sec_html)
        title_heading = re.search(rf'id="0*{num}\.([^"]+)"', html)
        english_title = (
            title_heading.group(1).replace("_", " ").strip()
            if title_heading
            else f"Chapter {num}"
        )
    else:
        # Standalone chapter page summary
        sum_match = re.search(
            r'id="Summary".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        summary_text = (
            clean_html(sum_match.group(1)) if sum_match else clean_html(html[:2000])
        )
        char_match = re.search(
            r'id="Characters".*?</h\d>(.*?)(?:<h\d|<div class="navbox")',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        characters = extract_characters_from_html(
            char_match.group(1) if char_match else html
        )
        english_title = page_title

    # Clean title
    english_title = re.sub(r"^\d+\.\s*", "", english_title).strip()

    vol_digits = re.search(r"Volume\s+(\d+)", page_title, flags=re.IGNORECASE)
    volume_num = int(vol_digits.group(1)) if vol_digits else None

    return {
        "_id": f"chapter_bleach_{num}",
        "manga_id": "manga_bleach",
        "series_id": "manga_bleach",
        "series_title": "Bleach",
        "chapter_number": num,
        "title": english_title,
        "volume": volume_num,
        "summary": summary_text,
        "characters_appeared": characters,
        "character_ids": [c["slug"] for c in characters],
        "source_url": f"https://bleach.fandom.com/wiki/{urllib.parse.quote(page_title)}",
        "scraped_at": datetime.now(timezone.utc),
    }


SCRAPER_DISPATCH = {
    "one_piece": scrape_one_piece_chapter,
    "naruto": scrape_naruto_chapter,
    "bleach": scrape_bleach_chapter,
    "attack_on_titan": scrape_aot_chapter,
    "dragon_ball": scrape_dragon_ball_chapter,
}


# ── RAG Document Generators ───────────────────────────────────────────────────


def generate_manga_markdown_doc(
    manga_cfg: dict, chapters: list[dict], output_file: Path
) -> str:
    """Generate a clean Markdown RAG document for a specific manga."""
    title = manga_cfg["title"]
    author = manga_cfg["author"]
    lines = [
        f"# {title} Canon Chapter Lore & Knowledge",
        "",
        f"> Official chapter guide, synopsis, and character appearances from {author}'s {title} manga.",
        "",
        "---",
        "",
    ]

    for ch in sorted(chapters, key=lambda x: x["chapter_number"]):
        num = ch["chapter_number"]
        ch_title = ch.get("title", f"Chapter {num}")
        lines.append(f"## Chapter {num}: {ch_title}")
        lines.append("")

        meta_parts = []
        if ch.get("volume"):
            meta_parts.append(f"**Volume**: {ch['volume']}")
        if ch.get("arc"):
            meta_parts.append(f"**Arc**: {ch['arc']}")
        if ch.get("release_date"):
            meta_parts.append(f"**Release Date**: {ch['release_date']}")

        if meta_parts:
            lines.append(" • ".join(meta_parts))
            lines.append("")

        chars = ch.get("characters_appeared", [])
        if chars:
            c_names = [c["name"] for c in chars[:30]]
            lines.append(f"### Characters in Chapter {num}")
            lines.append(", ".join(c_names))
            lines.append("")

        lines.append("### Story Events & Summary")
        summary_text = ch.get("summary") or "No synopsis available."
        lines.append(summary_text)
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Saved Markdown RAG document: {output_file} ({len(content)} chars)")
    return content


def generate_manga_pdf_doc(
    manga_cfg: dict, chapters: list[dict], output_file: Path
) -> Path | None:
    """Generate a dedicated PDF lore book for a specific manga."""
    if not HAS_REPORTLAB:
        logger.warning("reportlab is not installed. Skipping PDF generation.")
        return None

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
        fontSize=13,
        leading=17,
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

    manga_title = manga_cfg["title"]
    author = manga_cfg["author"]
    story = [
        Paragraph(
            f"{clean_text_for_pdf(manga_title)} Manga Canon & Chapter Lore", title_style
        ),
        Paragraph(
            f"Official Lore Knowledge Document for AI Chatbot RAG | Author: {author} | Generated: {datetime.now(timezone.utc).strftime('%B %Y')}",
            subtitle_style,
        ),
        HRFlowable(
            width="100%", thickness=1.5, color=colors.HexColor("#CBD5E0"), spaceAfter=12
        ),
    ]

    for ch in sorted(chapters, key=lambda x: x["chapter_number"]):
        num = ch["chapter_number"]
        t_raw = clean_text_for_pdf(ch.get("title", f"Chapter {num}"))

        meta_items = [f"<b>Chapter</b>: {num}"]
        if ch.get("volume"):
            meta_items.append(f"<b>Volume</b>: {ch['volume']}")
        if ch.get("arc"):
            meta_items.append(f"<b>Arc</b>: {clean_text_for_pdf(ch['arc'])}")
        if ch.get("release_date"):
            meta_items.append(
                f"<b>Released</b>: {clean_text_for_pdf(ch['release_date'])}"
            )

        meta_line = " &nbsp;|&nbsp; ".join(meta_items)

        story.append(Paragraph(f"Chapter {num}: {t_raw}", ch_heading_style))
        story.append(Paragraph(meta_line, meta_style))

        chars = ch.get("characters_appeared", [])
        if chars:
            c_names = [clean_text_for_pdf(c["name"]) for c in chars[:25]]
            char_str = ", ".join(c_names)
            if len(chars) > 25:
                char_str += f" and {len(chars) - 25} more"
            story.append(Paragraph("<b>Characters Appeared:</b>", char_heading_style))
            story.append(Paragraph(char_str, char_list_style))

        summary_raw = clean_text_for_pdf(ch.get("summary") or "")
        if summary_raw:
            for p in summary_raw.split("\n"):
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
        f"Saved PDF lore document: {output_file} ({output_file.stat().st_size} bytes)"
    )
    return output_file


async def save_manga_chapters_to_db(manga_cfg: dict, chapters: list[dict]) -> int:
    """Upsert chapters into MongoDB Atlas collection 'chapters' and ensure parent 'manga' record."""
    await connect_db()
    db = get_db()

    manga_id = manga_cfg["manga_id"]
    title = manga_cfg["title"]
    author = manga_cfg["author"]

    # 1. Ensure parent manga record in 'manga' collection
    await db["manga"].update_one(
        {"_id": manga_id},
        {
            "$setOnInsert": {
                "_id": manga_id,
                "name": title,
                "title": {"english": title, "romaji": title},
                "author": author,
                "type": "MANGA",
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    # 2. Upsert each chapter into 'chapters' collection
    saved_count = 0
    for ch in chapters:
        ch_doc = dict(ch)
        doc_id = ch_doc.pop("_id", None)
        update_op = {"$set": ch_doc}
        if doc_id:
            update_op["$setOnInsert"] = {"_id": doc_id}

        await db["chapters"].update_one(
            {"manga_id": ch["manga_id"], "chapter_number": ch["chapter_number"]},
            update_op,
            upsert=True,
        )
        saved_count += 1

    await close_db()
    logger.info(
        f"Upserted {saved_count} chapters into MongoDB Atlas 'chapters' for {title}"
    )
    return saved_count


# ── Main Orchestration ─────────────────────────────────────────────────────────


async def run_manga_scrape(
    manga_key: str,
    start: int,
    end: int,
    chapters_arg: str,
    delay: float,
    no_db: bool,
    output_dir: Path,
):
    """Scrape and build RAG lore for a single manga."""
    cfg = MANGA_CONFIGS[manga_key]
    scraper_fn = SCRAPER_DISPATCH[manga_key]

    if chapters_arg:
        chapter_nums = [
            int(c.strip()) for c in chapters_arg.split(",") if c.strip().isdigit()
        ]
    else:
        end_num = min(end, cfg["total_chapters"]) if end > 0 else cfg["total_chapters"]
        chapter_nums = list(range(start, end_num + 1))

    logger.info(
        f"[{cfg['title']}] Scraping {len(chapter_nums)} chapters (Ch. {chapter_nums[0]} to {chapter_nums[-1]})..."
    )

    scraped = []
    for idx, num in enumerate(chapter_nums):
        logger.info(
            f"[{cfg['title']}] [{idx+1}/{len(chapter_nums)}] Scraping Chapter {num}..."
        )
        ch = scraper_fn(num)
        if ch:
            scraped.append(ch)
            logger.info(
                f"  -> OK: '{ch.get('title')}' ({len(ch.get('characters_appeared', []))} chars, summary {len(ch.get('summary', ''))} chars)"
            )
        else:
            logger.warning(f"  -> SKIPPED / NOT FOUND: Chapter {num}")
        time.sleep(delay)

    if not scraped:
        logger.error(f"No chapters scraped for {cfg['title']}.")
        return

    out_dir = output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. JSON Export
    json_path = out_dir / cfg["json_name"]
    serializable = []
    for c in scraped:
        item = dict(c)
        if isinstance(item.get("scraped_at"), datetime):
            item["scraped_at"] = item["scraped_at"].isoformat()
        serializable.append(item)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved JSON export: {json_path}")

    # 2. Markdown RAG Document
    md_path = out_dir / cfg["md_name"]
    generate_manga_markdown_doc(cfg, scraped, md_path)

    # 3. Dedicated PDF Lore Document
    pdf_path = out_dir / cfg["pdf_name"]
    generate_manga_pdf_doc(cfg, scraped, pdf_path)

    # 4. Save to MongoDB Atlas
    if not no_db:
        await save_manga_chapters_to_db(cfg, scraped)

    print("\n" + "=" * 60)
    print(f"COMPLETED: {cfg['title']}")
    print(f"Total Chapters Processed: {len(scraped)}")
    print(f"Dedicated PDF Lore Book : {pdf_path}")
    print(f"Markdown RAG Document   : {md_path}")
    print(f"JSON Export             : {json_path}")
    if not no_db:
        print(
            f"MongoDB Atlas           : Stored in 'chapters' collection ({cfg['manga_id']})"
        )
    print("=" * 60 + "\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Unified Manga Chapter Scraper for One Piece, Naruto, Bleach, Attack on Titan, and Dragon Ball."
    )
    parser.add_argument(
        "--manga",
        type=str,
        default="naruto",
        help="Manga franchise to scrape: 'naruto', 'bleach', 'attack_on_titan' (aot), 'dragon_ball' (dbz), 'one_piece', or 'all'",
    )
    parser.add_argument(
        "--start", type=int, default=1, help="Starting chapter number (default: 1)"
    )
    parser.add_argument(
        "--end",
        type=int,
        default=5,
        help="Ending chapter number (inclusive, default: 5 for testing; 0 = all)",
    )
    parser.add_argument(
        "--chapters", type=str, default="", help="Specific chapters (e.g. '1,2,5,50')"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="Delay between requests in seconds (default: 0.35)",
    )
    parser.add_argument(
        "--no-db", action="store_true", help="Skip saving to MongoDB Atlas"
    )
    parser.add_argument(
        "--output-dir", type=str, default="data/manga_chapters", help="Output directory"
    )

    args = parser.parse_args()
    out_dir = Path(args.output_dir)

    target_input = args.manga.strip().lower()
    if target_input == "all":
        targets = list(MANGA_CONFIGS.keys())
    else:
        targets = [resolve_manga_key(target_input)]

    for t in targets:
        await run_manga_scrape(
            manga_key=t,
            start=args.start,
            end=args.end,
            chapters_arg=args.chapters,
            delay=args.delay,
            no_db=args.no_db,
            output_dir=out_dir,
        )


if __name__ == "__main__":
    asyncio.run(main())
