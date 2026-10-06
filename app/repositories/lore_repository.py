from app.config import LORE_VECTOR_INDEX_NAME
from app.db.mongo import get_db
from app.schemas.lore import LoreChunk, LoreQueryResult


async def insert_chunks(chunks: list[LoreChunk]) -> None:
    """Bulk insert a list of LoreChunk documents into the lore_chunks collection."""
    if not chunks:
        return

    db = get_db()
    docs = []
    for chunk in chunks:
        doc = chunk.model_dump() if hasattr(chunk, "model_dump") else chunk.dict()
        doc["_id"] = chunk.chunk_id
        docs.append(doc)

    await db["lore_chunks"].insert_many(docs)


async def delete_by_series(series_id: str) -> int:
    """Delete all lore chunks associated with a given series_id. Returns number of deleted chunks."""
    db = get_db()
    result = await db["lore_chunks"].delete_many({"series_id": series_id})
    return result.deleted_count


async def vector_search(
    query_embedding: list[float],
    series_id: str,
    top_k: int,
    character_ids: list[str] | None = None,
) -> list[LoreQueryResult]:
    """Perform a vector similarity search on lore_chunks using MongoDB Atlas $vectorSearch."""
    db = get_db()

    # Build Atlas Vector Search filter
    if character_ids:
        filter_doc = {
            "$and": [
                {"series_id": {"$eq": series_id}},
                {"character_ids": {"$in": character_ids}},
            ]
        }
    else:
        filter_doc = {
            "series_id": {"$eq": series_id}
        }

    # Ensure numCandidates is sufficiently larger than top_k for accurate ANN recall
    num_candidates = max(top_k * 10, 50)

    pipeline = [
        {
            "$vectorSearch": {
                "index": LORE_VECTOR_INDEX_NAME,
                "path": "embedding_vector",
                "queryVector": query_embedding,
                "numCandidates": num_candidates,
                "limit": top_k,
                "filter": filter_doc,
            }
        },
        {
            "$project": {
                "_id": 0,
                "chunk_text": 1,
                "score": {"$meta": "vectorSearchScore"},
                "section_title": 1,
                "series_id": 1,
            }
        },
    ]

    cursor = db["lore_chunks"].aggregate(pipeline)
    if hasattr(cursor, "__await__"):
        cursor = await cursor
    results = []

    async for doc in cursor:
        results.append(
            LoreQueryResult(
                chunk_text=doc.get("chunk_text", ""),
                score=float(doc.get("score", 0.0)),
                section_title=doc.get("section_title"),
                series_id=doc.get("series_id", series_id),
            )
        )

    return results


async def get_series_lore_status(series_id: str) -> dict:
    """Returns chunk count and list of distinct source files for a given series_id."""
    db = get_db()
    count = await db["lore_chunks"].count_documents({"series_id": series_id})
    distinct_files = await db["lore_chunks"].distinct("source_file", {"series_id": series_id})
    return {
        "series_id": series_id,
        "chunks_count": count,
        "source_files": distinct_files,
    }

