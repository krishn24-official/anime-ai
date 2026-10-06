import io
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from dataclasses import dataclass, field

from app.config import (
    LORE_CHUNK_OVERLAP,
    LORE_CHUNK_SIZE,
    LORE_EMBEDDING_MODEL,
    LORE_TOP_K,
)
from app.repositories import lore_repository
from app.schemas.lore import LoreChunk, LoreQueryResult
from app.backend.utils.slug import create_slug
from app.db.mongo import get_db

logger = logging.getLogger(__name__)


# ── Markdown-Aware Data Structures & Chunking ─────────────────────────────────


@dataclass
class MarkdownSection:
    title: str
    level: int
    content: str
    breadcrumbs: list[str] = field(default_factory=list)
    parent_title: str | None = None


@dataclass
class LoreTextChunk:
    section_title: str
    chunk_text: str


def normalize_markdown_spacing(text: str) -> str:
    """
    Defensive preprocessing for lore text extracted from PDFs, where PDF-to-text
    conversion frequently drops line breaks between elements that were on
    separate lines in the original source. This causes heading markers,
    horizontal rules, and bullet points to get glued onto the end of the
    preceding line, which silently breaks heading-based parsing (a glued
    '#### Eren Kruger' is invisible to a '^#{1,4}\\s+' regex, since it's no
    longer at the start of a line).

    Fixes three specific gluing patterns, confirmed present in real extracted
    PDF text:
    1. A heading marker (#, ##, ###, ####) stuck to the end of prior text,
       e.g. "Important Examples#### Eren Kruger" -> inserts a line break
       before the heading so it's detected correctly. The lookbehind
       excludes both '\\n' (already at line start, nothing to fix) AND '#'
       (otherwise this would incorrectly match partway through an
       already-correct '###' run and wrongly split it in half).
    2. A horizontal rule (---) stuck to the end of prior text,
       e.g. "Great Titan War.---" -> inserts a line break before it.
    3. A bullet dash stuck to the end of a prior sentence with no space,
       e.g. "Survey Corps- Zeke Yeager" -> inserts a line break before the
       dash. Deliberately conservative: only triggers when the dash is
       preceded by a letter/digit/punctuation (not whitespace) AND followed
       by a space plus a capital letter or digit — this avoids breaking
       legitimate compound words ("well-known") or number ranges ("18-25"),
       neither of which has a space immediately after the hyphen.

    NOTE: this does NOT fix two plain words glued with zero separator and no
    marker character (e.g. "Armor SerumResult" -> should be "Armor Serum\\nResult").
    That requires dictionary-based word segmentation to detect reliably and
    is out of scope here — such cases need manual correction in the source
    document.
    """
    text = re.sub(r'(?<![\n#])(#{1,4}\s)', r'\n\1', text)
    text = re.sub(r'(?<!\n)(---)', r'\n\1', text)
    text = re.sub(r'(?<=[a-zA-Z0-9.,;:])-(?=\s+[A-Z0-9])', r'\n-', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def looks_like_markdown(text: str) -> bool:
    """
    Quick heuristic to decide whether incoming lore text is markdown-structured.
    Requires at least 2 heading lines, since a single stray '#' shouldn't
    trigger markdown-mode parsing.
    """
    if not text:
        return False
    heading_re = re.compile(r"^#{1,4}\s+.+$", re.MULTILINE)
    return len(heading_re.findall(text)) >= 2


def _is_table_row(line: str) -> bool:
    """Detects markdown table syntax (e.g. '| Holder | Time | Notes |')."""
    return line.strip().startswith("|")


def _clean_section_content(raw: str) -> str:
    """Remove horizontal rules, table syntax, and excess whitespace from a section's body."""
    lines = raw.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            continue
        if _is_table_row(stripped):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def parse_markdown_sections(text: str) -> list[MarkdownSection]:
    """
    Parses markdown text into hierarchical MarkdownSection objects based on # headers.
    """
    heading_pattern = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))

    if not matches:
        cleaned = _clean_section_content(text)
        return [MarkdownSection(title="General Lore", level=1, content=cleaned)] if cleaned else []

    sections: list[MarkdownSection] = []

    # Handle preamble before first header if present
    if matches[0].start() > 0:
        preamble = _clean_section_content(text[: matches[0].start()])
        if preamble:
            sections.append(MarkdownSection(title="Overview", level=1, content=preamble))

    for idx, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        start_pos = match.end()
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        raw_content = text[start_pos:end_pos]
        cleaned_content = _clean_section_content(raw_content)

        sections.append(
            MarkdownSection(
                title=title,
                level=level,
                content=cleaned_content,
            )
        )

    return sections


def _attach_breadcrumbs(sections: list[MarkdownSection]) -> None:
    """
    Constructs hierarchical breadcrumb trails for each MarkdownSection.
    Example: ['Story Timeline', 'Trost Arc', 'First Transformation']
    """
    heading_stack: list[tuple[int, str]] = []  # (level, title)

    for sec in sections:
        # Pop any higher or equal level headings from stack
        while heading_stack and heading_stack[-1][0] >= sec.level:
            heading_stack.pop()

        parent_title = heading_stack[-1][1] if heading_stack else None
        heading_stack.append((sec.level, sec.title))

        sec.breadcrumbs = [h[1] for h in heading_stack]
        sec.parent_title = parent_title


def _is_safe_merge_target(current: MarkdownSection, next_section: MarkdownSection) -> bool:
    """
    Decides whether next_section is a safe place to fold current's small
    content into. Guards against merging unrelated sibling sections (e.g.
    'Trost Arc' and 'Female Titan Arc') just because they share a distant
    common ancestor.

    Safe cases:
    1. current has NO real content (a pure container heading) — always safe.
    2. next_section is a direct descendant (breadcrumb starts with current's).
    3. current and next_section are true siblings (same immediate parent).
    """
    if not current.content.strip():
        return True
    if next_section.breadcrumbs[: len(current.breadcrumbs)] == current.breadcrumbs:
        return True
    if current.breadcrumbs[:-1] == next_section.breadcrumbs[:-1]:
        return True
    return False


def merge_small_sections(
    sections: list[MarkdownSection],
    min_chars: int = 200,
) -> list[MarkdownSection]:
    """
    Sections with very little content embed poorly in isolation. Small sections
    are buffered and folded forward into the next section, but ONLY when that
    next section is a safe merge target (a true child or true sibling).

    Sections remain below min_chars when no safe merge target exists — a
    slightly-under-target but topically coherent chunk is better than a large
    chunk that silently bridges two unrelated arcs together.
    """
    if not sections:
        return []

    def flush_buffer_into(buffer: list[MarkdownSection], target: MarkdownSection) -> str:
        """Fold buffered small-section fragments into target's content."""
        prefix_parts = [
            f"{s.title}: {s.content}" for s in buffer if s.content.strip()
        ]
        if not prefix_parts:
            return target.content
        prefix = "\n\n".join(prefix_parts)
        return f"{prefix}\n\n{target.content}".strip() if target.content.strip() else prefix

    merged: list[MarkdownSection] = []
    buffer: list[MarkdownSection] = []

    for idx, section in enumerate(sections):
        is_last = idx == len(sections) - 1
        next_section = sections[idx + 1] if not is_last else None
        safe_next = next_section is not None and _is_safe_merge_target(section, next_section)

        if len(section.content) >= min_chars or not safe_next:
            section.content = flush_buffer_into(buffer, section)
            buffer = []
            merged.append(section)
        else:
            buffer.append(section)

    # Leftover buffered fragments at end attach to the last emitted section
    if buffer and merged:
        merged[-1].content = flush_buffer_into(buffer, merged[-1])
    elif buffer:
        last = buffer[-1]
        last.content = flush_buffer_into(buffer[:-1], last)
        merged.append(last)

    return merged


def _split_long_content(content: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Splits oversized section content using the same recursive-splitting
    priority as the generic chunk_text() (paragraph -> line -> sentence -> word).
    """
    if len(content) <= chunk_size:
        return [content] if content.strip() else []
    return chunk_text(text=content, chunk_size=chunk_size, overlap=overlap)


def chunk_markdown_text(
    text: str,
    chunk_size: int = LORE_CHUNK_SIZE,
    overlap: int = LORE_CHUNK_OVERLAP,
    min_section_chars: int = 200,
) -> list[LoreTextChunk]:
    """
    Full markdown-aware chunking pipeline:
    1. Parses headers into MarkdownSection hierarchy.
    2. Computes hierarchical breadcrumbs.
    3. Merges tiny sibling sections safely.
    4. Splits oversized sections into context-tagged LoreTextChunk items.

    Each chunk's chunk_text has its breadcrumb path prepended as a plain text
    header so the embedding model has context even for very short sections.

    Returns empty list if no markdown headings found — caller should fall back
    to plain chunk_text() instead.
    """
    sections = parse_markdown_sections(text)
    if not sections:
        return []

    _attach_breadcrumbs(sections)
    sections = merge_small_sections(sections, min_chars=min_section_chars)

    result: list[LoreTextChunk] = []

    for sec in sections:
        if not sec.content.strip():
            continue

        breadcrumb_str = " > ".join(sec.breadcrumbs)
        pieces = _split_long_content(sec.content, chunk_size, overlap)

        for piece in pieces:
            full_text = f"{breadcrumb_str}\n{piece}".strip()
            result.append(LoreTextChunk(section_title=breadcrumb_str, chunk_text=full_text))

    return result




# ── PDF Text Extraction ───────────────────────────────────────────────────────


def extract_text_from_pdf(file_bytes: bytes) -> list[dict[str, str]]:
    """
    Extracts text from an in-memory PDF file.

    Attempts to detect section headers (e.g. from outlines or distinct heading lines).
    Falls back to a single section with "General Lore" if no clear structure is found.

    Returns:
        list of {"section_title": str, "text": str}
    """
    if not file_bytes:
        raise ValueError("PDF file is empty")

    try:
        from pypdf import PdfReader
    except ImportError as err:
        logger.error("[lore_service] pypdf is not installed. Please run pip install -r requirements.txt")
        raise ImportError("pypdf package is required for PDF text extraction. Install with `pip install pypdf`.") from err

    try:
        reader = PdfReader(io.BytesIO(file_bytes))

    except Exception as err:
        logger.error(f"[lore_service] Error reading PDF: {err}")
        raise ValueError(f"Invalid or corrupted PDF file: {err}") from err

    if len(reader.pages) == 0:
        raise ValueError("PDF file contains no pages")

    # Extract all text page by page
    full_text_pages: list[str] = []
    for idx, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
            if page_text.strip():
                full_text_pages.append(page_text.strip())
        except Exception as err:
            logger.warning(f"[lore_service] Warning extracting text from page {idx + 1}: {err}")

    if not full_text_pages:
        raise ValueError("No extractable text found in the PDF")

    raw_full_text = "\n\n".join(full_text_pages)
    full_text = normalize_markdown_spacing(raw_full_text)

    # If the document contains markdown-style headings, preserve the full markdown text intact
    if looks_like_markdown(full_text):
        return [{"section_title": "Full Document", "text": full_text}]

    # Do not apply markdown normalization to the non-markdown fallback path
    full_text = raw_full_text

    # Attempt to detect section headers (e.g., lines like 'Chapter 1: ...', or ALL CAPS headings)
    section_pattern = re.compile(
        r"(?:^|\n\n)(?:Chapter\s+\d+[:\s]+|Section\s+\d+[:\s]+|[A-Z0-9\s]{4,40}:?\n)(.+?)(?:\n|$)",
        re.MULTILINE,
    )

    matches = list(section_pattern.finditer(full_text))

    if matches and len(matches) > 1:
        sections: list[dict[str, str]] = []
        for i, match in enumerate(matches):
            title = match.group(0).strip().strip(":").strip()
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            body = full_text[start_pos:end_pos].strip()
            if body:
                sections.append({"section_title": title, "text": body})

        if sections:
            return sections

    # Fallback: treat entire document as one section
    return [{"section_title": "General Lore", "text": full_text}]


# ── Recursive Character Text Chunking ─────────────────────────────────────────


def chunk_text(
    text: str,
    chunk_size: int = LORE_CHUNK_SIZE,
    overlap: int = LORE_CHUNK_OVERLAP,
) -> list[str]:
    """
    Implements recursive character splitting across separators:
    ["\n\n", "\n", ". ", " ", ""] to preserve semantic boundaries.

    Args:
        text: Input string to chunk
        chunk_size: Maximum character count per chunk
        overlap: Character overlap between consecutive chunks

    Returns:
        List of non-empty text chunk strings
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    separators = ["\n\n", "\n", ". ", " ", ""]

    def _split_text(t: str, seps: list[str]) -> list[str]:
        if not t.strip():
            return []
        if len(t) <= chunk_size:
            return [t.strip()]

        # Select the highest priority separator present in text
        sep = ""
        for s in seps:
            if s == "" or s in t:
                sep = s
                break

        remaining_seps = seps[seps.index(sep) + 1 :] if sep in seps else [""]

        if sep:
            raw_splits = t.split(sep)
            splits = [s for s in raw_splits if s]
        else:
            splits = list(t)

        final_chunks: list[str] = []
        current_doc: list[str] = []
        current_len = 0

        for split in splits:
            split_len = len(split) + (len(sep) if current_doc else 0)

            # If an individual split is larger than chunk_size, recurse on it
            if len(split) > chunk_size and remaining_seps:
                if current_doc:
                    merged = sep.join(current_doc).strip()
                    if merged:
                        final_chunks.append(merged)
                    current_doc = []
                    current_len = 0
                sub_chunks = _split_text(split, remaining_seps)
                final_chunks.extend(sub_chunks)
            elif current_len + split_len > chunk_size and current_doc:
                merged = sep.join(current_doc).strip()
                if merged:
                    final_chunks.append(merged)

                # Overlap calculation
                overlap_doc: list[str] = []
                overlap_len = 0
                for part in reversed(current_doc):
                    part_len = len(part) + (len(sep) if overlap_doc else 0)
                    if overlap_len + part_len <= overlap:
                        overlap_doc.insert(0, part)
                        overlap_len += part_len
                    else:
                        break

                current_doc = overlap_doc + [split]
                current_len = sum(len(p) for p in current_doc) + len(sep) * max(0, len(current_doc) - 1)
            else:
                current_doc.append(split)
                current_len += split_len

        if current_doc:
            merged = sep.join(current_doc).strip()
            if merged:
                final_chunks.append(merged)

        return final_chunks

    return _split_text(text, separators)


# ── Sentence-Transformers Embedder ────────────────────────────────────────────


class LoreEmbedder:
    """
    Wrapper around sentence-transformers embedding model.
    Instantiated once at module level for efficient inference.
    """

    def __init__(self, model_name: str = LORE_EMBEDDING_MODEL):
        self.model_name = model_name
        self._model: Any = None

    @property
    def model(self) -> Any:
        if self._model is None:
            logger.info(f"[lore_service] Loading embedding model: {self.model_name}")
            from sentence_transformers import SentenceTransformer

            try:
                self._model = SentenceTransformer(self.model_name, local_files_only=True)
            except Exception:
                self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_chunks(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Compute normalized vector embeddings for a batch of text chunks."""
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        """Compute a single normalized vector embedding for a query string."""
        if not text:
            return []
        embedding = self.model.encode(
            text,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embedding.tolist()


# Module-level singleton instance loaded once
lore_embedder = LoreEmbedder()


# ── Orchestrator ──────────────────────────────────────────────────────────────


def normalize_series_id(series_id: str) -> str:
    """
    Defensive normalization for series_id values arriving from the LLM agent,
    which may pass a human-readable title (e.g. "Attack on Titan") instead of
    the canonical snake_case series_id actually stored in MongoDB
    (e.g. "attack_on_titan"). Kept as fallback helper for resolve_series_id().
    """
    if not series_id:
        return series_id
    return series_id.strip().lower().replace(" ", "_").replace("-", "_")


async def resolve_series_id(raw_input: str, media_type: str | None = None) -> str:
    """
    Resolves a series identifier from the LLM agent into the canonical
    series_id format now stored in lore_chunks: the FULL prefixed document
    _id from the anime/manga/movies collections (e.g. "anime_naruto"), not
    a bare slug.

    Args:
        raw_input: Whatever the agent passed for series_id — could be a
            human title, nickname, or already-correct prefixed/unprefixed slug.
        media_type: Optional hint from the agent — "anime", "manga", or
            "movie" — when the user's question made the media type explicit
            (e.g. "in the manga, ..."). When None, resolution searches anime
            first, then movies, then manga, and returns the first match —
            this app defaults to anime when a title exists in multiple
            media types and the user didn't specify, since this is an
            anime-focused platform.

    Resolution order:
    1. Fast path: slugify raw_input (reuse existing create_slug()). If
       media_type is given, check only "{media_type}_{slug}" as a direct
       _id match in the corresponding collection. If media_type is None,
       check "anime_{slug}", then "movie_{slug}", then "manga_{slug}", in
       that priority order, and return the first that exists.
    2. Fallback: if no direct slug match, search titles/synonyms.
       - anime collection: title.english, title.romaji, title.japanese,
         synonyms[] — case-insensitive match against the RAW input.
       - movies collection: title field.
       - manga collection: name, native_name fields.
       Respect the media_type filter if given (search only that
       collection); otherwise search anime first, then movies, then manga,
       returning the first match — same anime-default priority as above.
    3. Last resort: if nothing matches anywhere, fall back to
       normalize_series_id() on the raw input and prefix it with "anime_"
       (the default media type for this platform), so query_lore still
       runs with SOME filter rather than raising an error. Log a warning
       when this fallback triggers, since it means resolution genuinely
       failed to find a real match.

    Returns the full prefixed series_id (e.g. "anime_naruto"), matching
    exactly what should now be stored in lore_chunks.series_id.
    """
    if not raw_input or not raw_input.strip():
        return ""

    db = get_db()
    clean_raw = raw_input.strip()

    collection_map = {
        "anime": ("anime", "anime_"),
        "movie": ("movies", "movie_"),
        "tv_series": ("tv_series", "tv_"),
        "tv": ("tv_series", "tv_"),
        "manga": ("manga", "manga_"),
    }

    # If raw_input already is a full prefixed _id (e.g. "anime_attack_on_titan", "tv_loki")
    for pfx, col in [("anime_", "anime"), ("movie_", "movies"), ("tv_", "tv_series"), ("manga_", "manga")]:
        if clean_raw.lower().startswith(pfx):
            doc = await db[col].find_one({"_id": clean_raw.lower()})
            if doc:
                return str(doc["_id"])

    # 1. Fast path: slugify raw_input
    base_raw = re.sub(r"^(anime|movie|tv_series|tv|manga)_", "", clean_raw, flags=re.IGNORECASE)
    slug = create_slug(base_raw)

    m_hint = media_type.lower().strip() if media_type else None
    if m_hint and m_hint in collection_map:
        col_name, pfx = collection_map[m_hint]
        doc = await db[col_name].find_one({"_id": f"{pfx}{slug}"})
        if doc:
            return str(doc["_id"])
    else:
        for m_type in ["anime", "movie", "tv_series", "manga"]:
            col_name, pfx = collection_map[m_type]
            doc = await db[col_name].find_one({"_id": f"{pfx}{slug}"})
            if doc:
                return str(doc["_id"])

    # 2. Fallback: Search titles / synonyms against clean_raw
    exact_pattern = re.compile(f"^{re.escape(clean_raw)}$", re.IGNORECASE)

    async def search_collection(m_type: str):
        col_name, _ = collection_map[m_type]
        if m_type == "anime":
            return await db[col_name].find_one({
                "$or": [
                    {"title.english": exact_pattern},
                    {"title.romaji": exact_pattern},
                    {"title.japanese": exact_pattern},
                    {"synonyms": exact_pattern},
                ],
                "is_deleted": False,
            })
        elif m_type == "movie":
            return await db[col_name].find_one({
                "$or": [
                    {"title": exact_pattern},
                    {"original_title": exact_pattern},
                ],
                "is_deleted": {"$ne": True},
            })
        elif m_type in ("tv_series", "tv"):
            return await db[col_name].find_one({
                "$or": [
                    {"title": exact_pattern},
                    {"original_title": exact_pattern},
                ],
                "is_deleted": {"$ne": True},
            })
        elif m_type == "manga":
            return await db[col_name].find_one({
                "$or": [
                    {"name": exact_pattern},
                    {"native_name": exact_pattern},
                ],
                "is_deleted": False,
            })
        return None

    types_to_search = [m_hint] if (m_hint and m_hint in collection_map) else ["anime", "movie", "tv_series", "manga"]
    for m_type in types_to_search:
        doc = await search_collection(m_type)
        if doc:
            return str(doc["_id"])

    # 3. Last resort fallback:
    fallback_slug = normalize_series_id(base_raw or raw_input)
    fallback_id = f"anime_{fallback_slug}"
    logger.warning(
        f"[lore_service] Could not resolve series_id for '{raw_input}' "
        f"(media_type={media_type}). Falling back to degraded ID: '{fallback_id}'"
    )
    return fallback_id


def process_lore_pdf(
    file_bytes: bytes,
    series_id: str,
    character_ids: list[str] | None = None,
    source_file: str = "uploaded_lore.pdf",
) -> list[LoreChunk]:
    """
    Orchestrates the complete ingestion workflow:
    1. Extracts structured sections from the in-memory PDF.
    2. Chunks text using recursive character splitting.
    3. Generates batched vector embeddings.
    4. Populates and returns LoreChunk instances ready for MongoDB insertion.
    """
    if not series_id:
        raise ValueError("series_id is required to process lore")

    series_id = series_id.strip()

    sections = extract_text_from_pdf(file_bytes)
    character_ids_clean = character_ids or []

    chunk_records: list[dict[str, str | None]] = []
    for section in sections:
        sec_title = section.get("section_title")
        sec_text = section.get("text", "")
        if not sec_text.strip():
            continue

        if looks_like_markdown(sec_text):
            md_chunks = chunk_markdown_text(
                sec_text,
                chunk_size=LORE_CHUNK_SIZE,
                overlap=LORE_CHUNK_OVERLAP,
            )
            for mc in md_chunks:
                chunk_records.append(
                    {
                        "section_title": mc.section_title,
                        "text": mc.chunk_text,
                    }
                )
        else:
            chunks = chunk_text(sec_text, chunk_size=LORE_CHUNK_SIZE, overlap=LORE_CHUNK_OVERLAP)
            for chunk in chunks:
                chunk_records.append(
                    {
                        "section_title": sec_title,
                        "text": chunk,
                    }
                )

    if not chunk_records:
        raise ValueError("No text chunks generated from PDF content")


    # Embed all text chunks in batches
    texts_to_embed = [str(r["text"]) for r in chunk_records]
    embeddings = lore_embedder.embed_chunks(texts_to_embed)

    lore_chunks: list[LoreChunk] = []
    now = datetime.now(timezone.utc)

    for record, embedding in zip(chunk_records, embeddings):
        lore_chunks.append(
            LoreChunk(
                chunk_id=str(uuid.uuid4()),
                series_id=series_id,
                character_ids=character_ids_clean,
                chunk_text=str(record["text"]),
                embedding_vector=embedding,
                source_file=source_file,
                section_title=record["section_title"],
                created_at=now,
            )
        )

    return lore_chunks


# ── Lore Query & LLM Context Formatting ───────────────────────────────────────


async def query_lore(
    query: str,
    series_id: str,
    media_type: str | None = None,
    character_ids: list[str] | None = None,
    top_k: int | None = None,
) -> list[LoreQueryResult]:
    """
    Queries vector-indexed lore for a series using semantic similarity.

    Args:
        query: User question or search query string
        series_id: Target series/anime ID
        media_type: Optional medium hint ("anime", "manga", or "movie")
        character_ids: Optional list of character IDs for pre-filtering
        top_k: Maximum number of relevant chunks to retrieve (defaults to config.LORE_TOP_K)

    Returns:
        List of LoreQueryResult sorted by relevance score descending
    """
    if not query or not query.strip():
        return []

    if not series_id:
        raise ValueError("series_id is required to query lore")

    series_id = await resolve_series_id(series_id, media_type=media_type)

    k = top_k if top_k is not None else LORE_TOP_K
    query_embedding = lore_embedder.embed_query(query)

    results = await lore_repository.vector_search(
        query_embedding=query_embedding,
        series_id=series_id,
        top_k=k,
        character_ids=character_ids,
    )

    # Sort descending by relevance score
    results.sort(key=lambda x: x.score, reverse=True)
    return results


def format_lore_context(results: list[LoreQueryResult]) -> str:
    """
    Formats a list of retrieved LoreQueryResult items into a clean markdown
    context block suitable for injection into an LLM prompt.

    Args:
        results: List of LoreQueryResult instances

    Returns:
        Formatted context string with section headings
    """
    if not results:
        return ""

    context_blocks: list[str] = []
    for idx, item in enumerate(results, 1):
        heading = f"### [Section: {item.section_title}]" if item.section_title else f"### [Lore Reference {idx}]"
        context_blocks.append(f"{heading}\n{item.chunk_text.strip()}")

    return "\n\n".join(context_blocks)

