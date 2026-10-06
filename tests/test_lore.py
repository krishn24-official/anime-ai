import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_current_admin
from app.schemas.lore import LoreChunk, LoreUploadResponse, LoreQueryResult
from app.repositories import lore_repository
from app.services.lore_service import chunk_text, LoreEmbedder, process_lore_pdf


def test_lore_schemas():
    chunk = LoreChunk(
        chunk_id="chunk-1",
        series_id="anime-123",
        character_ids=["char-1", "char-2"],
        chunk_text="Goku trains under Master Roshi on Kame House.",
        embedding_vector=[0.1] * 384,
        source_file="dragon_ball_lore.pdf",
        section_title="Early Life",
    )

    assert chunk.chunk_id == "chunk-1"
    assert chunk.series_id == "anime-123"
    assert len(chunk.character_ids) == 2
    assert len(chunk.embedding_vector) == 384
    assert chunk.section_title == "Early Life"
    assert isinstance(chunk.created_at, datetime)

    upload_res = LoreUploadResponse(
        series_id="anime-123",
        chunks_created=10,
        source_file="dragon_ball_lore.pdf",
    )
    assert upload_res.chunks_created == 10

    query_res = LoreQueryResult(
        chunk_text="Sample lore snippet",
        score=0.92,
        section_title="Origins",
        series_id="anime-123",
    )
    assert query_res.score == 0.92
    assert query_res.section_title == "Origins"


@pytest.mark.asyncio
async def test_insert_empty_chunks():
    # Should safely return without error
    await lore_repository.insert_chunks([])


def test_chunk_text_basic():
    text = "Paragraph 1 with some details.\n\nParagraph 2 with other details.\n\nParagraph 3 with final details."
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 60  # with margins


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_lore_embedder_mock():
    embedder = LoreEmbedder()
    mock_model = MagicMock()
    mock_model.encode.return_value = MagicMock(tolist=lambda: [[0.1, 0.2], [0.3, 0.4]])
    embedder._model = mock_model

    embeddings = embedder.embed_chunks(["hello", "world"])
    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]


@patch("app.services.lore_service.extract_text_from_pdf")
@patch("app.services.lore_service.lore_embedder")
def test_process_lore_pdf(mock_embedder, mock_extract):
    mock_extract.return_value = [
        {"section_title": "Chapter 1", "text": "This is a great story about a hero."}
    ]
    mock_embedder.embed_chunks.return_value = [[0.1] * 384]

    chunks = process_lore_pdf(
        file_bytes=b"%PDF-mock",
        series_id="series-abc",
        character_ids=["char-1"],
        source_file="test.pdf",
    )

    assert len(chunks) == 1
    assert chunks[0].series_id == "series-abc"
    assert chunks[0].character_ids == ["char-1"]
    assert chunks[0].source_file == "test.pdf"
    assert chunks[0].section_title == "Chapter 1"
    assert len(chunks[0].embedding_vector) == 384


@pytest.mark.asyncio
@patch("app.services.lore_service.process_lore_pdf")
async def test_admin_lore_routes(mock_process_pdf):
    # Override admin dependency
    app.dependency_overrides[get_current_admin] = lambda: {"_id": "admin_123", "is_admin": True}

    mock_process_pdf.return_value = [
        LoreChunk(
            chunk_id="chk-1",
            series_id="series-test",
            character_ids=["char-1"],
            chunk_text="Test lore chunk text",
            embedding_vector=[0.1] * 384,
            source_file="lore.pdf",
            section_title="Lore Section",
        )
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test upload
        files = {"file": ("lore.pdf", b"%PDF-mock-data", "application/pdf")}
        data = {"series_id": "series-test", "character_ids": "char-1, char-2"}

        response = await client.post("/admin/lore/upload", files=files, data=data)
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["series_id"] == "series-test"
        assert res_json["chunks_created"] == 1
        assert res_json["source_file"] == "lore.pdf"

        # 2. Test status endpoint
        status_res = await client.get("/admin/lore/series-test/status")
        assert status_res.status_code == 200
        status_json = status_res.json()
        assert status_json["series_id"] == "series-test"
        assert status_json["chunks_count"] == 1
        assert "lore.pdf" in status_json["source_files"]

        # 3. Test delete endpoint
        del_res = await client.delete("/admin/lore/series-test")
        assert del_res.status_code == 200
        del_json = del_res.json()
        assert del_json["series_id"] == "series-test"
        assert del_json["chunks_deleted"] == 1

        # Check status after deletion
        status_after = await client.get("/admin/lore/series-test/status")
        assert status_after.status_code == 200
        assert status_after.json()["chunks_count"] == 0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.repositories.lore_repository.vector_search")
@patch("app.services.lore_service.lore_embedder")
async def test_query_lore(mock_embedder, mock_vector_search):
    from app.services.lore_service import query_lore

    mock_embedder.embed_query.return_value = [0.1] * 384
    mock_vector_search.return_value = [
        LoreQueryResult(chunk_text="Chunk B", score=0.75, section_title="Sec B", series_id="s1"),
        LoreQueryResult(chunk_text="Chunk A", score=0.95, section_title="Sec A", series_id="s1"),
    ]

    results = await query_lore("Who is the main hero?", series_id="s1", top_k=2)
    assert len(results) == 2
    # Verify sorted descending by score
    assert results[0].score == 0.95
    assert results[0].chunk_text == "Chunk A"
    assert results[1].score == 0.75


def test_format_lore_context():
    from app.services.lore_service import format_lore_context

    results = [
        LoreQueryResult(chunk_text="Goku was raised by Grandpa Gohan.", score=0.9, section_title="Origin", series_id="dbz"),
        LoreQueryResult(chunk_text="He transformed into a Great Ape.", score=0.8, section_title=None, series_id="dbz"),
    ]

    formatted = format_lore_context(results)
    assert "### [Section: Origin]" in formatted
    assert "Goku was raised by Grandpa Gohan." in formatted
    assert "### [Lore Reference 2]" in formatted
    assert "He transformed into a Great Ape." in formatted

    # Test empty
    assert format_lore_context([]) == ""


@pytest.mark.asyncio
@patch("app.services.lore_service.query_lore")
@patch("app.services.lore_service.format_lore_context")
async def test_agent_query_lore_tool(mock_format, mock_query):
    from app.services.agent_tools import execute_tool

    mock_query.return_value = [
        LoreQueryResult(chunk_text="Itachi secretly protected the leaf village.", score=0.98, section_title="Truth", series_id="naruto")
    ]
    mock_format.return_value = "### [Section: Truth]\nItachi secretly protected the leaf village."

    result = await execute_tool("query_lore", {"query": "Why did Itachi eliminate his clan?", "series_id": "naruto"})
    assert "Itachi secretly protected the leaf village." in result


def test_agent_tool_definitions_contains_query_lore():
    from app.services.agent_tool_definitions import AGENT_TOOLS

    declarations = AGENT_TOOLS[0]["function_declarations"]
    tool_names = [fn["name"] for fn in declarations]
    assert "query_lore" in tool_names

    query_lore_decl = next(fn for fn in declarations if fn["name"] == "query_lore")
    assert "query" in query_lore_decl["parameters"]["properties"]
    assert "series_id" in query_lore_decl["parameters"]["properties"]
    assert "character_ids" in query_lore_decl["parameters"]["properties"]
    assert "query" in query_lore_decl["parameters"]["required"]
    assert "series_id" in query_lore_decl["parameters"]["required"]


def test_looks_like_markdown():
    from app.services.lore_service import looks_like_markdown

    assert looks_like_markdown("# Story Timeline\n## Arc 1\nSome text") is True
    assert looks_like_markdown("This is just plain text with no headers.") is False
    assert looks_like_markdown("") is False
    # Single heading should NOT trigger markdown mode
    assert looks_like_markdown("# Just one heading") is False


def test_chunk_markdown_text():
    from app.services.lore_service import chunk_markdown_text

    md_text = """# Attack on Titan Lore

## Story Timeline

### Trost Arc
Eren transforms into the Attack Titan for the first time during the Battle of Trost District. After being swallowed by a titan, he emerges in titan form and carries a massive boulder to seal the breach in Wall Rose. This event marks a turning point in humanitys fight against the titans, as it proves that titan powers can be used to protect humanity.

### Female Titan Arc
The Survey Corps embarks on the 57th Expedition beyond Wall Rose into titan territory. Commander Erwin orchestrates a plan to capture the Female Titan, suspected to be Annie Leonhart, a fellow graduate of the 104th Training Corps. The expedition reveals the existence of titan shifters hiding among the military ranks.
"""

    chunks = chunk_markdown_text(md_text, chunk_size=500, overlap=50)
    assert len(chunks) >= 2
    assert any("Attack on Titan Lore > Story Timeline > Trost Arc" in c.section_title for c in chunks)
    assert any("Female Titan Arc" in c.section_title for c in chunks)
    for c in chunks:
        assert c.chunk_text.startswith("Attack on Titan Lore")


@patch("app.services.lore_service.extract_text_from_pdf")
@patch("app.services.lore_service.lore_embedder")
def test_process_lore_pdf_markdown_branching(mock_embedder, mock_extract):
    mock_extract.return_value = [
        {
            "section_title": "General Lore",
            "text": "# Series Arc\n## Battle of Shiganshina\nThe final battle to reclaim Wall Maria begins.",
        }
    ]
    mock_embedder.embed_chunks.return_value = [[0.1] * 384]

    chunks = process_lore_pdf(
        file_bytes=b"%PDF-mock-md",
        series_id="aot",
        source_file="aot_lore.pdf",
    )

    assert len(chunks) == 1
    assert chunks[0].series_id == "aot"
    assert "Series Arc > Battle of Shiganshina" in chunks[0].section_title



