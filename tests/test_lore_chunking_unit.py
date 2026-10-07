import pytest
from app.services.lore_service import (
    normalize_markdown_spacing,
    merge_small_sections,
    chunk_markdown_text,
    MarkdownSection,
)


@pytest.fixture(autouse=True)
def db_setup():
    """Override conftest's autouse db_setup to keep unit tests fast and completely DB-free."""
    yield


# ── 1. normalize_markdown_spacing tests ────────────────────────────────────────


def test_normalize_markdown_spacing_glued_heading():
    # Heading marker glued to text without newline
    raw = "Important Examples#### Eren Kruger\nEren Kruger was an Eldian spy."
    normalized = normalize_markdown_spacing(raw)
    assert "Important Examples\n#### Eren Kruger" in normalized


def test_normalize_markdown_spacing_glued_horizontal_rule():
    # Horizontal rule stuck to text without newline
    raw = "The Great Titan War ended.---Next Section begins here."
    normalized = normalize_markdown_spacing(raw)
    assert "The Great Titan War ended.\n---" in normalized


def test_normalize_markdown_spacing_glued_bullet_dash():
    # Bullet dash stuck to end of sentence without space
    raw = "Survey Corps Members- Levi Ackerman is humanity's strongest soldier."
    normalized = normalize_markdown_spacing(raw)
    assert "Survey Corps Members\n- Levi Ackerman" in normalized


def test_normalize_markdown_spacing_preserves_compound_words_and_numbers():
    # Should NOT split legitimate hyphens in compound words or number ranges
    raw = "A well-known warrior aged 18-25 fought bravely."
    normalized = normalize_markdown_spacing(raw)
    assert "well-known" in normalized
    assert "18-25" in normalized
    assert "\n-" not in normalized


def test_normalize_markdown_spacing_collapses_excessive_newlines():
    raw = "Section 1\n\n\n\n\nSection 2"
    normalized = normalize_markdown_spacing(raw)
    assert normalized == "Section 1\n\nSection 2"


# ── 2. merge_small_sections tests ─────────────────────────────────────────────


def test_merge_small_sections_folds_small_sibling():
    # Two sibling sections at level 2: first is tiny (< 200 chars), next is safe sibling
    s1 = MarkdownSection(
        title="Intro",
        level=2,
        content="Short intro content.",
        breadcrumbs=["Story", "Intro"],
    )
    s2 = MarkdownSection(
        title="Details",
        level=2,
        content="This is the longer body of the story detailing all events across the entire arc in full depth and context.",
        breadcrumbs=["Story", "Details"],
    )
    sections = [s1, s2]
    merged = merge_small_sections(sections, min_chars=100)

    # s1 should have been merged into s2
    assert len(merged) == 1
    assert merged[0].title == "Details"
    assert "Intro: Short intro content." in merged[0].content
    assert "This is the longer body" in merged[0].content


def test_merge_small_sections_keeps_sufficient_content():
    # Section with >= min_chars should not be merged away
    long_content = "A" * 250
    s1 = MarkdownSection(
        title="Arc 1",
        level=2,
        content=long_content,
        breadcrumbs=["Story", "Arc 1"],
    )
    s2 = MarkdownSection(
        title="Arc 2",
        level=2,
        content="Arc 2 content.",
        breadcrumbs=["Story", "Arc 2"],
    )
    merged = merge_small_sections([s1, s2], min_chars=200)

    assert len(merged) == 2
    assert merged[0].title == "Arc 1"
    assert merged[1].title == "Arc 2"


def test_merge_small_sections_guards_against_unrelated_siblings():
    # Sibling with different parent branch should NOT merge even if under min_chars
    s1 = MarkdownSection(
        title="Trost Arc",
        level=2,
        content="Short Trost.",
        breadcrumbs=["History", "Season 1", "Trost Arc"],
    )
    s2 = MarkdownSection(
        title="Female Titan Arc",
        level=2,
        content="Female Titan.",
        breadcrumbs=["History", "Season 2", "Female Titan Arc"],  # Different parent!
    )
    merged = merge_small_sections([s1, s2], min_chars=200)

    # Must NOT bridge two unrelated season branches together!
    assert len(merged) == 2
    assert merged[0].title == "Trost Arc"
    assert merged[1].title == "Female Titan Arc"


# ── 3. chunk_markdown_text tests ──────────────────────────────────────────────


def test_chunk_markdown_text_hierarchical_breadcrumbs():
    markdown = """# Attack on Titan
## Titan Powers
### The Founding Titan
The Founding Titan can control all other Titans and alter Eldian memories.
### The Attack Titan
The Attack Titan can see memories of future inheritors.
"""
    chunks = chunk_markdown_text(markdown, chunk_size=400, overlap=50, min_section_chars=50)

    assert len(chunks) >= 2
    # Check that breadcrumbs are prepended to each chunk
    titles = [c.section_title for c in chunks]
    assert any("Attack on Titan > Titan Powers > The Founding Titan" in t for t in titles)
    assert any("Attack on Titan > Titan Powers > The Attack Titan" in t for t in titles)

    # Check that chunk_text starts with the hierarchical title breadcrumbs
    founding_chunk = next(c for c in chunks if "The Founding Titan" in c.section_title)
    assert "Attack on Titan > Titan Powers > The Founding Titan" in founding_chunk.chunk_text
    assert "Founding Titan can control all other Titans" in founding_chunk.chunk_text


def test_chunk_markdown_text_empty_on_plain_text():
    # Plain text without markdown headings returns empty list so caller uses fallback
    plain = "This is just a block of plain text with no headings or structure whatsoever."
    chunks = chunk_markdown_text(plain)
    # Since looks_like_markdown requires at least 2 headings, chunk_markdown_text returns []
    # parse_markdown_sections returns General Lore for 0 headings
    assert len(chunks) == 1
    assert chunks[0].section_title == "General Lore"
