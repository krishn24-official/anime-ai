from fastapi import APIRouter, HTTPException
from app.db.mongo import get_db

router = APIRouter()


# 🔥 Helper: convert MongoDB document → JSON safe
def serialize(doc):
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


def serialize_list(docs):
    return [serialize(doc) for doc in docs]


# 🔹 Get all characters
@router.get("/characters")
async def get_characters():
    db = get_db()

    try:
        characters = await db.characters.find().to_list(100)
        return serialize_list(characters)
    except Exception as e:
        print("❌ ERROR:", e)
        raise HTTPException(status_code=500, detail="Failed to fetch characters")


# 🔹 Get single character
@router.get("/characters/{char_id}")
async def get_character(char_id: str):
    db = get_db()

    try:
        character = await db.characters.find_one({"_id": char_id})

        if not character:
            raise HTTPException(status_code=404, detail="Character not found")

        return serialize(character)

    except Exception as e:
        print("❌ ERROR:", e)
        raise HTTPException(status_code=500, detail="Failed to fetch character")


# 🔹 Get all relationships of a character
@router.get("/relationships/{char_id}")
async def get_relationships(char_id: str):
    db = get_db()

    try:
        relations = await db.relationships.find({
            "source_id": char_id
        }).to_list(100)

        return serialize_list(relations)

    except Exception as e:
        print("❌ ERROR:", e)
        raise HTTPException(status_code=500, detail="Failed to fetch relationships")


# 🔹 Get family only
@router.get("/characters/{char_id}/family")
async def get_family(char_id: str):
    db = get_db()

    family_types = ["father", "mother", "son", "daughter", "wife", "husband"]

    try:
        relations = await db.relationships.find({
            "source_id": char_id,
            "relationship": {"$in": family_types}
        }).to_list(100)

        return serialize_list(relations)

    except Exception as e:
        print("❌ ERROR:", e)
        raise HTTPException(status_code=500, detail="Failed to fetch family")