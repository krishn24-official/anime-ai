"""
Reads character_data_template.csv (filled in manually) and bulk-updates
the characters collection. Only non-empty cells are applied — empty
cells are skipped, leaving the existing DB value untouched.

Run:
    python -m app.backend.ingestion.anime.bulk_update_characters

Validates game_properties, birth_day, birth_month, gender, role, status
before writing anything, and warns about anything unrecognized.
"""
import asyncio
import csv

from app.db.mongo import connect_db, close_db, get_db
from app.services.game_properties import GAME_PROPERTIES

INPUT_FILE = "character_data_template.csv"

VALID_GAME_PROPERTY_KEYS = set(GAME_PROPERTIES.keys())

VALID_STATUS = {"alive", "deceased", "unknown"}
VALID_GENDER = {"male", "female", "unknown"}
VALID_ROLE = {"main", "supporting", "background"}

VALID_BOOL_STRINGS = {
    "true": True, "yes": True, "1": True,
    "false": False, "no": False, "0": False,
}


def _split_list(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    return [v.strip() for v in value.split(";") if v.strip()]


def _parse_bool(value: str):
    if not value or not value.strip():
        return None
    return VALID_BOOL_STRINGS.get(value.strip().lower())


def _parse_int(value: str):
    if not value or not value.strip():
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _validate_row(row: dict, row_num: int) -> list[str]:
    """Returns a list of warning strings for this row (doesn't block import)."""
    warnings = []
    name = row.get("name", "")

    # game_properties
    game_props = _split_list(row.get("game_properties", ""))
    for prop in game_props:
        if prop not in VALID_GAME_PROPERTY_KEYS:
            warnings.append(
                f"Row {row_num} ({name}): unknown game_property "
                f"'{prop}' — check spelling against game_properties.py"
            )

    # status
    status = row.get("status", "").strip().lower()
    if status and status not in VALID_STATUS:
        warnings.append(
            f"Row {row_num} ({name}): unusual status '{status}' "
            f"(expected: alive, deceased, unknown) — will still be saved"
        )

    # gender
    gender = row.get("gender", "").strip().lower()
    if gender and gender not in VALID_GENDER:
        warnings.append(
            f"Row {row_num} ({name}): unusual gender '{gender}' "
            f"(expected: male, female, unknown) — will still be saved"
        )

    # role
    role = row.get("role", "").strip().lower()
    if role and role not in VALID_ROLE:
        warnings.append(
            f"Row {row_num} ({name}): unusual role '{role}' "
            f"(expected: main, supporting, background) — will still be saved"
        )

    # birth_day
    birth_day = row.get("birth_day", "").strip()
    if birth_day:
        day = _parse_int(birth_day)
        if day is None or not (1 <= day <= 31):
            warnings.append(
                f"Row {row_num} ({name}): invalid birth_day '{birth_day}' "
                f"(expected 1-31) — will be skipped"
            )

    # birth_month
    birth_month = row.get("birth_month", "").strip()
    if birth_month:
        month = _parse_int(birth_month)
        if month is None or not (1 <= month <= 12):
            warnings.append(
                f"Row {row_num} ({name}): invalid birth_month '{birth_month}' "
                f"(expected 1-12) — will be skipped"
            )

    # has_hair
    has_hair = row.get("has_hair", "").strip()
    if has_hair and has_hair.lower() not in VALID_BOOL_STRINGS:
        warnings.append(
            f"Row {row_num} ({name}): has_hair value '{has_hair}' "
            f"not recognized as TRUE/FALSE — will be skipped"
        )

    return warnings


def _build_update(row: dict) -> dict:
    """Build a $set dict containing only the fields that have values."""
    update = {}

    # --- Top-level scalar fields ---
    if row.get("native_name", "").strip():
        update["native_name"] = row["native_name"].strip()

    birth_day = _parse_int(row.get("birth_day", ""))
    if birth_day is not None and 1 <= birth_day <= 31:
        update["birth_day"] = birth_day

    birth_month = _parse_int(row.get("birth_month", ""))
    if birth_month is not None and 1 <= birth_month <= 12:
        update["birth_month"] = birth_month

    if row.get("gender", "").strip():
        update["gender"] = row["gender"].strip().lower()

    if row.get("role", "").strip():
        update["role"] = row["role"].strip().lower()

    if row.get("status", "").strip():
        update["status"] = row["status"].strip().lower()

    if row.get("species", "").strip():
        update["species"] = row["species"].strip().lower()

    # --- List fields ---
    affiliations = _split_list(row.get("affiliations", ""))
    if affiliations:
        update["affiliations"] = affiliations

    abilities = _split_list(row.get("abilities", ""))
    if abilities:
        update["abilities"] = abilities

    forms = _split_list(row.get("forms", ""))
    if forms:
        update["forms"] = forms

    tags = _split_list(row.get("tags", ""))
    if tags:
        update["tags"] = tags

    game_properties = _split_list(row.get("game_properties", ""))
    if game_properties:
        update["game_properties"] = [
            p for p in game_properties if p in VALID_GAME_PROPERTY_KEYS
        ]

    # --- Nested: physical.* ---
    if row.get("height", "").strip():
        update["physical.height"] = row["height"].strip()

    if row.get("hair_color", "").strip():
        update["physical.hair_color"] = row["hair_color"].strip()

    has_hair = _parse_bool(row.get("has_hair", ""))
    if has_hair is not None:
        update["physical.has_hair"] = has_hair

    # --- Nested: images.* ---
    if row.get("image_profile", "").strip():
        update["images.profile"] = row["image_profile"].strip()

    if row.get("image_banner", "").strip():
        update["images.banner"] = row["image_banner"].strip()

    return update


async def main():
    print("🚀 Starting bulk character update from CSV...")

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"❌ {INPUT_FILE} not found. Run export_character_csv.py first.")
        return

    print(f"📊 Read {len(rows)} rows from {INPUT_FILE}\n")

    # --- Validation pass ---
    all_warnings = []
    for i, row in enumerate(rows, start=2):  # row 1 is header
        all_warnings.extend(_validate_row(row, i))

    if all_warnings:
        print(f"⚠️  {len(all_warnings)} warning(s) found:\n")
        for w in all_warnings:
            print(f"  - {w}")
        print()

        confirm = input("Continue with import anyway? (y/n): ").strip().lower()
        if confirm != "y":
            print("❌ Import cancelled.")
            return
        print()

    # --- Update pass ---
    await connect_db()
    db = get_db()
    col = db["characters"]

    updated = 0
    skipped = 0
    not_found = 0

    for row in rows:
        char_id = row.get("_id", "").strip()

        if not char_id:
            continue

        update = _build_update(row)

        if not update:
            skipped += 1
            continue

        result = await col.update_one(
            {"_id": char_id},
            {"$set": update}
        )

        if result.matched_count:
            updated += 1
            print(f"  ✅ Updated: {row.get('name')} ({char_id}) — {list(update.keys())}")
        else:
            not_found += 1
            print(f"  ❌ Not found in DB: {char_id} ({row.get('name')})")

    await close_db()

    print(f"\n🏁 Done. Updated: {updated}, Skipped (no changes): {skipped}, Not found: {not_found}")


if __name__ == "__main__":
    asyncio.run(main())