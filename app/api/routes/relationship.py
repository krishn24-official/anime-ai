from fastapi import APIRouter

from app.services.relationship_service import (
    fetch_relationships,
    fetch_family,
    fetch_friends,
    fetch_team,
    fetch_mentors
)

router = APIRouter(
    prefix="/relationships",
    tags=["Relationships"]
)

@router.get("/{character_id}")

async def get_relationships(
    character_id: str
):

    return await (
        fetch_relationships(
            character_id
        )
    )

@router.get("/{character_id}/family")

async def get_family(
    character_id: str
):

    return await (
        fetch_family(
            character_id
        )
    )

@router.get("/{character_id}/friends")

async def get_friends(
    character_id: str
):

    return await (
        fetch_friends(
            character_id
        )
    )

@router.get("/{character_id}/team")

async def get_team(
    character_id: str
):

    return await (
        fetch_team(
            character_id
        )
    )

@router.get("/{character_id}/mentors")

async def get_mentors(
    character_id: str
):

    return await (
        fetch_mentors(
            character_id
        )
    )
