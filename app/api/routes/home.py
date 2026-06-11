from fastapi import APIRouter

from app.services.home_service import (
    fetch_home_today
)

router = APIRouter(
    prefix="/home",
    tags=["Home"]
)


@router.get("/today")
async def get_home_today():

    return await (
        fetch_home_today()
    )

