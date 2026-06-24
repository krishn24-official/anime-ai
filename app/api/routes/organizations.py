from fastapi import APIRouter, HTTPException, Query
from typing import Literal

from app.services.organization_service import (
    fetch_all_organizations,
    fetch_organization_details,
    fetch_organization_search,
    fetch_organizations_by_anime,
)

router = APIRouter(
    prefix="/organizations",
    tags=["Organizations"]
)

# Supported organization type options
OrgType = Literal[
    "organization", "village", "pirate_crew", "military", 
    "school", "family_clan", "country", "group", "title_holders"
]

@router.get("")
async def get_organizations(
    type: OrgType | None = Query(None, description="Filter organizations by type"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Page size limit")
):
    return await fetch_all_organizations(type_filter=type, page=page, limit=limit)

@router.get("/search")
async def search(
    q: str = Query(..., description="Query string to search organizations")
):
    return await fetch_organization_search(q)

@router.get("/anime/{anime_id}")
async def get_by_anime(
    anime_id: str
):
    return await fetch_organizations_by_anime(anime_id)

@router.get("/{id}")
async def get_organization(
    id: str
):
    org = await fetch_organization_details(id)
    if not org:
        raise HTTPException(
            status_code=404,
            detail="Organization not found"
        )
    return org
