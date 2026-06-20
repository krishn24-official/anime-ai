"""
Reads relationship_data_template.csv and creates/updates relationship
documents in MongoDB — auto-generating BOTH directions (source->target
and target->source) using the inverse relationship map.

Run:
    python -m app.backend.ingestion.relationships.bulk_update_relationships

Validates that source_id and target_id exist in the characters
collection before creating anything, and warns about unknown
relationship words (not blocking — relationship is free-form).
"""
import asyncio
import csv
import re

from app.db.mongo import connect_db, close_db, get_db
from app.services.relationship_inverse_map import get_inverse_relationship, is_symmetric

INPUT_FILE = "relationship_data_template.csv"


def _slug(text: str) -> str:
    """Simplify a character _id into a short slug for building relationship _ids."""
    text = text.replace("char_", "")
    text = re.sub(r"[^a-z0-9_]", "", text.lower())
    return text


def _make_rel_id(source_id: str, target_id: str, relationship: str) -> str:
    rel_word = re.sub(r"[^a-z0-9_]", "_", relationship.strip().lower())
    return f"rel_{_slug(source_id)}_{_slug(target_id)}_{rel_word}"


async def _validate_rows(rows: list[dict], known_ids: set[str]) -> list[str]:
    warnings = []

    for i, row in enumerate(rows, start=2):
        source_id = row.get("source_id", "").strip()
        target_id = row.get("target_id", "").strip()
        relationship = row.get("relationship", "").strip()

        if not source_id or not target_id or not relationship:
            if source_id or target_id or relationship:
                warnings.append(f"Row {i}: incomplete row, missing required field(s) — skipped")
            continue

        if source_id not in known_ids:
            warnings.append(f"Row {i}: source_id '{source_id}' not found in characters collection")

        if target_id not in known_ids:
            warnings.append(f"Row {i}: target_id '{target_id}' not found in characters collection")

        if source_id == target_id:
            warnings.append(f"Row {i}: source_id and target_id are the same ('{source_id}') — skipped")

    return warnings


def _build_relationship_pair(row: dict) -> list[dict]:
    """Returns 1 or 2 relationship documents (forward + inverse)."""
    source_id = row["source_id"].strip()
    target_id = row["target_id"].strip()
    relationship = row["relationship"].strip().lower()
    rel_type = row.get("type", "").strip() or None
    context = row.get("context", "").strip() or None
    explicit_inverse = row.get("inverse_relationship", "").strip() or None

    forward_id = _make_rel_id(source_id, target_id, relationship)
    inverse_relationship = get_inverse_relationship(relationship, explicit_inverse)
    inverse_id = _make_rel_id(target_id, source_id, inverse_relationship)

    forward_doc = {
        "_id": forward_id,
        "source_id": source_id,
        "target_id": target_id,
        "relationship": relationship,
        "type": rel_type,
        "context": context,
        "is_deleted": False,
        "deleted_at": None,
        "inverse_of": inverse_id,
    }

    # If symmetric and no explicit inverse override, forward == inverse
    # relationship word — still create a separate doc for the reverse
    # direction so queries from either side work.
    inverse_doc = {
        "_id": inverse_id,
        "source_id": target_id,
        "target_id": source_id,
        "relationship": inverse_relationship,
        "type": rel_type,
        "context": context,
        "is_deleted": False,
        "deleted_at": None,
        "inverse_of": forward_id,
    }

    return [forward_doc, inverse_doc]


async def main():
    print("🚀 Starting bulk relationship import from CSV...")

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if any(r.values())]
    except FileNotFoundError:
        print(f"❌ {INPUT_FILE} not found. Run export_relationship_csv.py first.")
        return

    # Drop the example/template row if present
    rows = [
        r for r in rows
        if not (r.get("source_id", "").strip() == "char_naruto_uzumaki"
                and r.get("target_id", "").strip() == "char_sasuke_uchiha"
                and "(example)" in r.get("source_name", ""))
    ]

    print(f"📊 Read {len(rows)} rows from {INPUT_FILE}\n")

    await connect_db()
    db = get_db()

    # Validate source/target ids exist
    known_ids = set(
        doc["_id"] for doc in
        await db["characters"].find({}, {"_id": 1}).to_list(None)
    )

    warnings = await _validate_rows(rows, known_ids)

    if warnings:
        print(f"⚠️  {len(warnings)} warning(s) found:\n")
        for w in warnings:
            print(f"  - {w}")
        print()

        confirm = input("Continue with import anyway? (y/n): ").strip().lower()
        if confirm != "y":
            print("❌ Import cancelled.")
            await close_db()
            return
        print()

    col = db["relationships"]

    created = 0
    skipped = 0

    for row in rows:
        source_id = row.get("source_id", "").strip()
        target_id = row.get("target_id", "").strip()
        relationship = row.get("relationship", "").strip()

        if not source_id or not target_id or not relationship or source_id == target_id:
            skipped += 1
            continue

        if source_id not in known_ids or target_id not in known_ids:
            skipped += 1
            continue

        docs = _build_relationship_pair(row)

        for doc in docs:
            await col.replace_one(
                {"_id": doc["_id"]},
                doc,
                upsert=True
            )
            created += 1

        print(f"  ✅ {docs[0]['source_id']} --{docs[0]['relationship']}--> {docs[0]['target_id']}  "
              f"(+ inverse: --{docs[1]['relationship']}-->)")

    await close_db()

    print(f"\n🏁 Done. Relationship documents created/updated: {created}, Rows skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())