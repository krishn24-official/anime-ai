"""
Exports characters to a CSV template you can fill in manually, then
import back via bulk_update_characters.py.

Run:
    python -m app.backend.ingestion.anime.export_character_csv

Produces: character_data_template.csv in the project root.

CSV columns:
  _id                 -- DO NOT EDIT, used to match the document
  name                -- DO NOT EDIT, for your reference only
  native_name          -- character's native-language name
  birth_day            -- 1-31
  birth_month           -- 1-12
  gender                -- male / female / unknown
  role                  -- main / supporting / background
  status                -- alive / deceased / unknown
  species               -- human / titan / devil / etc.
  height                -- e.g. "166 cm" or "5'7\""
  hair_color            -- e.g. "Black", "Blonde", "Silver"
  has_hair              -- TRUE / FALSE
  image_profile         -- profile image URL
  image_banner          -- banner image URL
  affiliations          -- semicolon-separated, e.g. "Survey Corps;104th Cadet Corps"
  abilities             -- semicolon-separated, e.g. "Titan Shifter;Hand-to-hand combat"
  forms                 -- semicolon-separated, e.g. "Base;Titan Form;Awakened"
  tags                  -- semicolon-separated, free-form labels
  game_properties        -- semicolon-separated, must match keys in game_properties.py

Leave a cell EMPTY to skip updating that field for that character.
Only non-empty cells overwrite existing DB values when imported.
"""
import asyncio
import csv

from app.db.mongo import connect_db, close_db, get_db

OUTPUT_FILE = "character_data_template.csv"

FIELDNAMES = [
    "_id",
    "name",
    "native_name",
    "birth_day",
    "birth_month",
    "gender",
    "role",
    "status",
    "species",
    "height",
    "hair_color",
    "has_hair",
    "image_profile",
    "image_banner",
    "affiliations",
    "abilities",
    "forms",
    "tags",
    "game_properties",
]


def _join(value):
    if not value:
        return ""
    if isinstance(value, list):
        return ";".join(str(v) for v in value)
    return str(value)


def _val(value):
    """Convert None to empty string, keep everything else as-is."""
    if value is None:
        return ""
    return value


async def main():
    print("🚀 Exporting characters to CSV...")

    await connect_db()
    db = get_db()

    characters = await db["characters"].find(
        {"is_deleted": {"$ne": True}},
        {
            "_id": 1,
            "name": 1,
            "native_name": 1,
            "birth_day": 1,
            "birth_month": 1,
            "gender": 1,
            "role": 1,
            "status": 1,
            "species": 1,
            "physical": 1,
            "images": 1,
            "affiliations": 1,
            "abilities": 1,
            "forms": 1,
            "tags": 1,
            "game_properties": 1,
        }
    ).sort("name", 1).to_list(None)

    await close_db()

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for char in characters:
            physical = char.get("physical") or {}
            images = char.get("images") or {}

            writer.writerow({
                "_id": char["_id"],
                "name": char.get("name", ""),
                "native_name": _val(char.get("native_name")),
                "birth_day": _val(char.get("birth_day")),
                "birth_month": _val(char.get("birth_month")),
                "gender": _val(char.get("gender")),
                "role": _val(char.get("role")),
                "status": _val(char.get("status")),
                "species": _val(char.get("species")),
                "height": _val(physical.get("height")),
                "hair_color": _val(physical.get("hair_color")),
                "has_hair": _val(physical.get("has_hair")),
                "image_profile": _val(images.get("profile")),
                "image_banner": _val(images.get("banner")),
                "affiliations": _join(char.get("affiliations")),
                "abilities": _join(char.get("abilities")),
                "forms": _join(char.get("forms")),
                "tags": _join(char.get("tags")),
                "game_properties": _join(char.get("game_properties")),
            })

    print(f"✅ Exported {len(characters)} characters to {OUTPUT_FILE}")
    print("📝 Fill in the empty cells, then run bulk_update_characters.py")


if __name__ == "__main__":
    asyncio.run(main())