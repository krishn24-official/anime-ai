"""
Exports existing relationships to a CSV (for reference/editing) and
also creates a blank template row set you can copy for adding NEW
relationships.

Run:
    python -m app.backend.ingestion.relationships.export_relationship_csv

Produces: relationship_data_template.csv

CSV columns:
  source_name           -- character name (for your reference, lookup happens by source_id)
  source_id              -- character _id, e.g. "char_naruto_uzumaki" (REQUIRED)
  target_name             -- character name (for your reference)
  target_id                -- character _id, e.g. "char_sasuke_uchiha" (REQUIRED)
  relationship              -- e.g. "father", "teammate", "rival" (REQUIRED)
  type                      -- category, e.g. "family", "team", "academy", "romantic" (optional)
  context                    -- free text note, e.g. "Met during the Chunin Exams" (optional)
  inverse_relationship         -- override the auto-inverse, e.g. "son" instead of default "child" (optional)

For NEW relationships: leave source_id/target_id referencing existing
character _ids (from your characters collection), fill in relationship,
and the import script will auto-create BOTH directions (source->target
and target->source) unless the relationship is one-directional by nature.
"""
import asyncio
import csv

from app.db.mongo import connect_db, close_db, get_db

OUTPUT_FILE = "relationship_data_template.csv"

FIELDNAMES = [
    "source_name",
    "source_id",
    "target_name",
    "target_id",
    "relationship",
    "type",
    "context",
    "inverse_relationship",
]


async def main():
    print("🚀 Exporting existing relationships to CSV...")

    await connect_db()
    db = get_db()

    relationships = await db["relationships"].find(
        {"is_deleted": {"$ne": True}}
    ).sort("source_id", 1).to_list(None)

    # Build a name lookup for readability
    characters = await db["characters"].find(
        {}, {"_id": 1, "name": 1}
    ).to_list(None)
    name_map = {c["_id"]: c.get("name", "") for c in characters}

    await close_db()

    # Deduplicate: only show ONE direction per pair+relationship in the
    # export (the inverse is implied), to avoid cluttering the sheet.
    seen_pairs = set()
    rows = []

    for rel in relationships:
        source_id = rel.get("source_id")
        target_id = rel.get("target_id")
        relationship = rel.get("relationship", "")

        # Skip if we've already exported the inverse of this pair
        pair_key = tuple(sorted([source_id, target_id])) + (relationship,)
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        rows.append({
            "source_name": name_map.get(source_id, ""),
            "source_id": source_id,
            "target_name": name_map.get(target_id, ""),
            "target_id": target_id,
            "relationship": relationship,
            "type": rel.get("type") or "",
            "context": rel.get("context") or "",
            "inverse_relationship": "",   # leave blank, already in DB
        })

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

        # Add a few blank template rows at the bottom for new entries
        writer.writerow({})
        writer.writerow({
            "source_name": "(example) Naruto Uzumaki",
            "source_id": "char_naruto_uzumaki",
            "target_name": "(example) Sasuke Uchiha",
            "target_id": "char_sasuke_uchiha",
            "relationship": "rival",
            "type": "academy",
            "context": "",
            "inverse_relationship": "",
        })

    print(f"✅ Exported {len(rows)} existing relationships to {OUTPUT_FILE}")
    print("📝 Add new rows at the bottom (use the example row as a template)")
    print("📝 Then run bulk_update_relationships.py")


if __name__ == "__main__":
    asyncio.run(main())