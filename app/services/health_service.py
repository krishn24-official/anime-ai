from app.repositories.health_repository import (
    get_database_stats
)


async def fetch_health():

    stats = await (
        get_database_stats()
    )

    return {

        "status": "ok",

        **stats
    }