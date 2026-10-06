"""
Standalone test script to verify the Lore RAG pipeline end-to-end.

Usage:
    python scripts/test_lore_pipeline.py --pdf path/to/lore.pdf --series_id naruto-123 --question "Why did Itachi join the Akatsuki?"
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.mongo import close_db, connect_db
from app.repositories import lore_repository
from app.services import lore_service


def parse_args():
    parser = argparse.ArgumentParser(description="Manually test and debug Lore RAG ingestion and retrieval pipeline.")
    parser.add_argument("--pdf", type=str, required=True, help="Path to local PDF file")
    parser.add_argument("--series_id", type=str, required=True, help="Target series_id (e.g. naruto, dbz, one-piece)")
    parser.add_argument("--question", type=str, required=True, help="Test question or semantic query")
    parser.add_argument("--character_ids", type=str, default=None, help="Optional comma-separated character IDs")
    parser.add_argument("--top_k", type=int, default=5, help="Number of chunks to retrieve (default: 5)")
    return parser.parse_args()


async def run_pipeline(pdf_path: str, series_id: str, question: str, character_ids_raw: str | None, top_k: int):
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"\n[ERROR] PDF file not found at: {pdf_path}")
        return

    print("=" * 70)
    print(" ANIME AI -- LORE RAG PIPELINE TEST HARVEST")
    print("=" * 70)

    print(f" PDF Source : {pdf_file.name} ({pdf_file.stat().st_size} bytes)")
    print(f" Series ID  : {series_id}")
    print(f" Question   : '{question}'")
    print(f" Top-K      : {top_k}")

    # Parse character IDs if provided
    char_ids = None
    if character_ids_raw:
        char_ids = [c.strip() for c in character_ids_raw.split(",") if c.strip()]
        print(f" Filters    : character_ids = {char_ids}")
    print("-" * 70)

    # 1. Read PDF file bytes
    with open(pdf_file, "rb") as f:
        file_bytes = f.read()

    # 2. Process & Chunk & Embed
    print("\n[1/4] Processing PDF and generating embeddings...")
    chunks = lore_service.process_lore_pdf(
        file_bytes=file_bytes,
        series_id=series_id,
        character_ids=char_ids,
        source_file=pdf_file.name,
    )

    print(f"      Successfully generated {len(chunks)} chunk(s).")
    print("\n--- Chunk Previews ---")
    for idx, chunk in enumerate(chunks, 1):
        preview = chunk.chunk_text[:100].replace("\n", " ") + ("..." if len(chunk.chunk_text) > 100 else "")
        sec = chunk.section_title or "General Lore"
        print(f" [{idx:02d}] Section: '{sec}' | Chars: {len(chunk.chunk_text)} | Vector Dim: {len(chunk.embedding_vector)}")
        print(f"      Preview: \"{preview}\"")

    # 3. Connect to DB and Insert Chunks
    print("\n[2/4] Connecting to MongoDB and storing chunks...")
    await connect_db()
    try:
        deleted = await lore_repository.delete_by_series(series_id)
        if deleted > 0:
            print(f"      Cleared {deleted} existing chunk(s) for series '{series_id}'.")

        await lore_repository.insert_chunks(chunks)
        print(f"      Inserted {len(chunks)} new chunk(s) into 'lore_chunks' collection.")
        # 4. Query Vector Search (polling briefly for Atlas asynchronous Lucene sync)
        print(f"\n[3/4] Querying vector search for: '{question}'...")
        results = []
        max_attempts = 8
        for attempt in range(1, max_attempts + 1):
            results = await lore_service.query_lore(
                query=question,
                series_id=series_id,
                character_ids=char_ids,
                top_k=top_k,
            )
            if results:
                break
            if attempt < max_attempts:
                print(f"      Waiting for Atlas Search indexing sync (attempt {attempt}/{max_attempts}, sleeping 2s)...")
                await asyncio.sleep(2)

        print(f"      Retrieved {len(results)} matching chunk(s).")
        print("\n--- Search Results ---")
        for rank, res in enumerate(results, 1):
            sec = res.section_title or "General Lore"
            print(f" Rank #{rank} | Relevance Score: {res.score:.4f} | Section: '{sec}'")
            print(f" Text: {res.chunk_text.strip()}\n")

        # 5. Formatted LLM Context
        print("-" * 70)
        print("[4/4] Final Formatted Context for LLM Prompt:")
        print("-" * 70)
        formatted_context = lore_service.format_lore_context(results)
        if formatted_context:
            print(formatted_context)
        else:
            print("(Empty context - no chunks returned)")
        print("=" * 70)

    finally:
        await close_db()


def main():
    args = parse_args()
    asyncio.run(
        run_pipeline(
            pdf_path=args.pdf,
            series_id=args.series_id,
            question=args.question,
            character_ids_raw=args.character_ids,
            top_k=args.top_k,
        )
    )


if __name__ == "__main__":
    main()
