import httpx

from app.config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_IMAGE_BASE_URL


def image_url(path: str | None, size: str = "w500") -> str | None:
    if not path:
        return None
    return f"{TMDB_IMAGE_BASE_URL}/{size}{path}"


async def _get(path: str, params: dict | None = None) -> dict | None:
    if not TMDB_API_KEY:
        print("[tmdb_client] TMDB_API_KEY not configured")
        return None

    url = f"{TMDB_BASE_URL}{path}"

    request_params = dict(params or {})
    request_params["api_key"] = TMDB_API_KEY

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=request_params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        print(f"[tmdb_client] HTTP error for {path}: {e.response.status_code} - {e.response.text[:200]}")
        return None
    except Exception as e:
        import traceback
        print(f"[tmdb_client] error for {path}: {type(e).__name__}: {e!r}")
        traceback.print_exc()
        return None


# --- Lists ---

async def get_trending_movies(page: int = 1) -> list[dict]:
    data = await _get("/trending/movie/week", {"page": page})
    return (data or {}).get("results", [])


async def get_trending_tv(page: int = 1) -> list[dict]:
    data = await _get("/trending/tv/week", {"page": page})
    return (data or {}).get("results", [])


async def search_movie(query: str) -> list[dict]:
    data = await _get("/search/movie", {"query": query})
    return (data or {}).get("results", [])


async def search_tv(query: str) -> list[dict]:
    data = await _get("/search/tv", {"query": query})
    return (data or {}).get("results", [])


# --- Details ---

async def get_movie_details(tmdb_id: int) -> dict | None:
    return await _get(
        f"/movie/{tmdb_id}",
        {"append_to_response": "credits,videos"}
    )


async def get_tv_details(tmdb_id: int) -> dict | None:
    return await _get(
        f"/tv/{tmdb_id}",
        {"append_to_response": "credits,videos"}
    )