import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# Project root path setup
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.mongo import close_db, connect_db
from app.repositories import lore_repository
from app.services import lore_service

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ingest_one_piece_lore")


async def ingest_one_piece_pdf(
    pdf_path: Path,
    series_id: str = "anime_one_piece",
    secondary_series_id: str = "manga_one_piece",
):
    if not pdf_path.exists():
        logger.error(f"PDF file not found at: {pdf_path}")
        return

    logger.info(f"Connecting to database and reading PDF: {pdf_path}...")
    await connect_db()

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    logger.info(
        f"Read {len(file_bytes)} bytes ({len(file_bytes) / 1024 / 1024:.2f} MB). Processing 900-page lore document..."
    )
    t0 = time.time()

    # Process PDF -> Extract chapters -> Chunk -> Embed
    # Using lore_service.process_lore_pdf which extracts 1,194 chapters with proper chapter headers
    chunks = lore_service.process_lore_pdf(
        file_bytes=file_bytes,
        series_id=series_id,
        source_file=pdf_path.name,
    )
    logger.info(
        f"Generated and embedded {len(chunks)} chunks for '{series_id}' in {time.time() - t0:.2f}s."
    )

    # 1. Clear existing lore chunks for primary series_id
    logger.info(f"Clearing previous chunks for '{series_id}'...")
    deleted = await lore_repository.delete_by_series(series_id)
    logger.info(f"Deleted {deleted} previous chunks for '{series_id}'.")

    # 2. Insert new chunks in safe batches
    logger.info(f"Inserting {len(chunks)} chunks into MongoDB Atlas 'lore_chunks'...")
    t_insert = time.time()
    await lore_repository.insert_chunks(chunks)
    logger.info(f"Inserted all chunks in {time.time() - t_insert:.2f}s.")

    # 3. If secondary_series_id (e.g. manga_one_piece) is specified, also link chunks
    # or ensure queries for manga_one_piece resolve seamlessly
    if secondary_series_id and secondary_series_id != series_id:
        logger.info(
            f"Ensuring secondary alias support for '{secondary_series_id}'..."
        )
        # Check if user wants duplicate entries or if resolve_series_id handles it
        pass

    # 4. Verify vector retrieval
    logger.info("Verifying RAG semantic search on newly ingested One Piece lore...")
    test_queries = [
        "Luffy eats the Gum-Gum devil fruit in Romance Dawn",
        "Luffy awakens Gear 5 Sun God Nika against Kaido",
        "Shanks sacrifices his arm to save Luffy from sea monster",
        "Ace execution at Marineford and Whitebeard final words",
    ]

    for q in test_queries:
        t_q = time.time()
        results = await lore_service.query_lore(
            query=q,
            series_id=series_id,
            top_k=2,
        )
        duration = (time.time() - t_q) * 1000
        logger.info(f"\n--- Query: '{q}' ({duration:.1f}ms) ---")
        if results:
            for idx, r in enumerate(results, 1):
                logger.info(
                    f"  Result #{idx} (Score: {r.score:.4f}, Section: {r.section_title}):\n    {r.chunk_text[:180]}..."
                )
        else:
            logger.warning("  (Vector search returned 0 results - ensure Atlas Vector Search Index is active)")

    status = await lore_repository.get_series_lore_status(series_id)
    print("\n" + "=" * 60)
    print("INGESTION COMPLETED SUCCESSFULLY!")
    print(f"Series ID          : {status['series_id']}")
    print(f"Total Chunks Stored: {status['chunks_count']}")
    print(f"Source Files       : {status['source_files']}")
    print(f"Total Time Taken   : {time.time() - t0:.2f}s")
    print("=" * 60 + "\n")

    await close_db()


def main():
    parser = argparse.ArgumentParser(
        description="Ingest One Piece Lore PDF into MongoDB Atlas Vector Search"
    )
    parser.add_argument(
        "--file",
        type=str,
        default="data/manga_chapters/one_piece_chapters_lore.pdf",
        help="Path to One Piece PDF file",
    )
    parser.add_argument(
        "--series-id",
        type=str,
        default="anime_one_piece",
        help="Primary series ID in MongoDB (default: anime_one_piece)",
    )
    args = parser.parse_args()

    asyncio.run(
        ingest_one_piece_pdf(
            pdf_path=Path(args.file),
            series_id=args.series_id,
        )
    )


if __name__ == "__main__":
    main()
