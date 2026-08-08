"""
audit_character_name_collisions.py
=====================================
One-time audit script: find character name collisions that may signal
past silent overwrites caused by the name-slug dedup bug.

What this does
--------------
1. Groups all non-deleted character documents by normalized name
   (lowercase, stripped, collapsed whitespace).
2. For names shared by 2+ documents → these are fine IF each document has
   a distinct source_metadata.anilist_id.  Reports them for awareness.
3. For names with only 1 document → cannot directly detect a past overwrite
   (the destroyed data is gone), but flags names worth manually re-checking
   if they are "high-collision-risk" names (very short, single-word, known
   to appear in multiple anime).
4. Finds all characters that have NO anilist_id at all (admin-created entries
   never linked to AniList) — these are the only ones still subject to the
   name+birthday fallback path.
5. Outputs a structured report and optionally writes a CSV for manual review.

What this does NOT do
---------------------
- It does NOT auto-correct anything.
- It cannot reconstruct data that was already overwritten — re-run ingestion
  for the affected anime (see recover_dr_stone_characters.py for the pattern).

Usage
-----
    python -m app.scripts.audit_character_name_collisions
    python -m app.scripts.audit_character_name_collisions --csv report.csv
"""

import asyncio
import argparse
import csv
import re
import sys
import io
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db, get_db


def normalize_name(name: str) -> str:
    """Lowercase, strip, collapse internal whitespace."""
    return re.sub(r"\s+", " ", name.strip().lower())


def get_anilist_id(doc: dict) -> int | None:
    """Extract the AniList character id from either storage location."""
    sm = doc.get("source_metadata", {})
    # Primary (new schema): source_metadata.anilist_id
    aid = sm.get("anilist_id")
    if aid:
        return int(aid)
    # Fallback (old nested schema): source_metadata.anilist.id
    aid = sm.get("anilist", {}).get("id")
    if aid:
        return int(aid)
    return None


async def main(csv_path: str | None = None):
    print("🔍 Starting character name collision audit...")
    await connect_db()
    db = get_db()

    # ── Fetch all non-deleted characters ─────────────────────────────────────
    print("  Fetching all characters from DB...")
    all_chars = await db["characters"].find(
        {"is_deleted": {"$ne": True}},
        {
            "_id": 1,
            "name": 1,
            "source_metadata": 1,
            "anime_ids": 1,
            "birth_day": 1,
            "birth_month": 1,
        },
    ).to_list(length=None)

    total = len(all_chars)
    print(f"  Total characters: {total}\n")

    # ── Group by normalized name ──────────────────────────────────────────────
    by_name: dict[str, list[dict]] = defaultdict(list)
    no_anilist_id: list[dict] = []

    for doc in all_chars:
        name = doc.get("name") or ""
        if not name:
            continue
        key = normalize_name(name)
        by_name[key].append(doc)

        if get_anilist_id(doc) is None:
            no_anilist_id.append(doc)

    # ── Analysis ─────────────────────────────────────────────────────────────

    # Category A: names with 2+ docs — all fine if each has a distinct anilist_id
    shared_names_ok: list[tuple[str, list[dict]]] = []
    # Category B: names with 2+ docs where some docs share an anilist_id (data anomaly)
    shared_names_conflict: list[tuple[str, list[dict]]] = []
    # Category C: names with 2+ docs where at least one doc has NO anilist_id
    shared_names_no_id: list[tuple[str, list[dict]]] = []

    for norm_name, docs in by_name.items():
        if len(docs) < 2:
            continue

        anilist_ids = [get_anilist_id(d) for d in docs]
        ids_with_value = [i for i in anilist_ids if i is not None]
        has_any_null_id = any(i is None for i in anilist_ids)
        has_duplicate_id = len(ids_with_value) != len(set(ids_with_value))

        if has_duplicate_id:
            shared_names_conflict.append((norm_name, docs))
        elif has_any_null_id:
            shared_names_no_id.append((norm_name, docs))
        else:
            shared_names_ok.append((norm_name, docs))

    # ── Report ────────────────────────────────────────────────────────────────

    print("=" * 70)
    print("  AUDIT REPORT — Character Name Collisions")
    print("=" * 70)

    print(f"\n📊 Summary")
    print(f"  Total characters          : {total}")
    print(f"  Distinct normalized names : {len(by_name)}")
    print(f"  Characters without anilist_id : {len(no_anilist_id)}")
    print(f"\n  Names shared by 2+ docs:")
    print(f"    ✅ All have distinct anilist_ids (safe)  : {len(shared_names_ok)}")
    print(f"    ⚠️  At least one has no anilist_id       : {len(shared_names_no_id)}")
    print(f"    ❌ Duplicate anilist_id across docs (BUG): {len(shared_names_conflict)}")

    # --- Category OK (informational) ---
    if shared_names_ok:
        print(f"\n{'─' * 70}")
        print(f"  ✅ SAFE SHARED NAMES ({len(shared_names_ok)}) — distinct anilist_ids, no action needed")
        print(f"{'─' * 70}")
        for norm_name, docs in sorted(shared_names_ok, key=lambda x: x[0]):
            ids = [f"{d['_id']}(al:{get_anilist_id(d)})" for d in docs]
            print(f"  '{norm_name}': {', '.join(ids)}")

    # --- Category with missing anilist_id (needs attention) ---
    if shared_names_no_id:
        print(f"\n{'─' * 70}")
        print(
            f"  ⚠️  SHARED NAMES WITH MISSING ANILIST_ID ({len(shared_names_no_id)})"
            f" — manual review recommended"
        )
        print(f"{'─' * 70}")
        for norm_name, docs in sorted(shared_names_no_id, key=lambda x: x[0]):
            print(f"\n  Name: '{norm_name}'")
            for doc in docs:
                aid = get_anilist_id(doc) or "NONE"
                print(
                    f"    _id={doc['_id']}  anilist_id={aid}"
                    f"  anime_ids={doc.get('anime_ids', [])}"
                )

    # --- Category conflict (actual bug indicator) ---
    if shared_names_conflict:
        print(f"\n{'─' * 70}")
        print(
            f"  ❌ ANILIST_ID CONFLICTS ({len(shared_names_conflict)})"
            f" — two documents share the same anilist_id (likely a dedup artifact)"
        )
        print(f"{'─' * 70}")
        for norm_name, docs in sorted(shared_names_conflict, key=lambda x: x[0]):
            print(f"\n  Name: '{norm_name}'")
            for doc in docs:
                aid = get_anilist_id(doc) or "NONE"
                print(
                    f"    _id={doc['_id']}  anilist_id={aid}"
                    f"  anime_ids={doc.get('anime_ids', [])}"
                )
    else:
        print(f"\n  ✅ No anilist_id conflicts detected.")

    # --- Characters with no anilist_id ---
    if no_anilist_id:
        print(f"\n{'─' * 70}")
        print(f"  🔗 CHARACTERS WITHOUT ANILIST_ID ({len(no_anilist_id)}) — admin-created, no AniList link")
        print(f"{'─' * 70}")
        for doc in sorted(no_anilist_id, key=lambda d: d.get("name", "")):
            print(f"  {doc['_id']}: {doc.get('name', '?')}")

    # --- Recommendation ---
    print(f"\n{'=' * 70}")
    print("  RECOMMENDATIONS")
    print(f"{'=' * 70}")
    if shared_names_conflict:
        print("  ❌ Duplicate anilist_id documents found. These indicate the dedup bug")
        print("     created two documents for the same character. Investigate each and")
        print("     soft-delete the spurious one, or re-run ingestion after verifying.")
    if shared_names_no_id:
        print("  ⚠️  Characters with missing anilist_id sharing a name with another")
        print("     character may have been affected by the old name-slug dedup.")
        print("     Check their anime_ids and data manually; re-run ingestion for any")
        print("     anime where you suspect a character was overwritten.")
    if not shared_names_conflict and not shared_names_no_id:
        print("  ✅ No suspicious collisions found. The database appears clean.")

    # ── Optional CSV output ───────────────────────────────────────────────────
    if csv_path:
        rows = []
        for norm_name, docs in by_name.items():
            if len(docs) < 2:
                continue
            for doc in docs:
                aid = get_anilist_id(doc)
                rows.append({
                    "normalized_name": norm_name,
                    "_id": doc["_id"],
                    "anilist_id": aid or "",
                    "anime_ids": ";".join(doc.get("anime_ids", [])),
                    "birth_day": doc.get("birth_day", ""),
                    "birth_month": doc.get("birth_month", ""),
                    "category": (
                        "conflict" if aid and any(
                            get_anilist_id(d) == aid for d in docs if d["_id"] != doc["_id"]
                        )
                        else "no_anilist_id" if not aid
                        else "safe"
                    ),
                })

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["normalized_name", "_id", "anilist_id", "anime_ids",
                            "birth_day", "birth_month", "category"],
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n  📄 CSV written to: {csv_path}")

    await close_db()
    print("\n✅ Audit complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit character name collisions")
    parser.add_argument("--csv", default=None, help="Optional path to write CSV report")
    args = parser.parse_args()
    asyncio.run(main(csv_path=args.csv))
