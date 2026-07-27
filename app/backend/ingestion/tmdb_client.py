import asyncio
import ssl

import httpx

from app.config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_IMAGE_BASE_URL

MAX_RETRIES = 4
RETRY_DELAY = 2  # seconds

# ── Shared client (reuses TCP + TLS connections) ─────────
_client: httpx.AsyncClient | None = None


def _get_ssl_context() -> ssl.SSLContext:
    """Permissive SSL context for Windows environments with
    restrictive certificate stores."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def get_client() -> httpx.AsyncClient:
    """Return the shared httpx client, creating it on first call."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=15.0),
            verify=_get_ssl_context(),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30,
            ),
            follow_redirects=True,
        )
    return _client


async def close_client():
    """Close the shared client (call on shutdown)."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


# ── Helpers ──────────────────────────────────────────────

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

    client = await get_client()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.get(url, params=request_params)
            response.raise_for_status()
            return response.json()
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * attempt
                print(f"[tmdb_client] retry {attempt}/{MAX_RETRIES} for {path} ({type(e).__name__}), waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                print(f"[tmdb_client] failed after {MAX_RETRIES} retries for {path}: {type(e).__name__}")
                return None
        except httpx.HTTPStatusError as e:
            print(f"[tmdb_client] HTTP error for {path}: {e.response.status_code} - {e.response.text[:200]}")
            return None
        except Exception as e:
            print(f"[tmdb_client] error for {path}: {type(e).__name__}: {e!r}")
            return None

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


# --- Discovery (bulk) ---

async def discover_movies(page: int = 1, sort_by: str = "popularity.desc", **filters) -> dict:
    """Discover movies with filtering. Returns full paginated response."""
    params = {"page": page, "sort_by": sort_by, **filters}
    return await _get("/discover/movie", params) or {"results": [], "total_pages": 0, "total_results": 0}


async def discover_tv(page: int = 1, sort_by: str = "popularity.desc", **filters) -> dict:
    """Discover TV series with filtering. Returns full paginated response."""
    params = {"page": page, "sort_by": sort_by, **filters}
    return await _get("/discover/tv", params) or {"results": [], "total_pages": 0, "total_results": 0}


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


async def get_person_details(tmdb_id: int) -> dict | None:
    return await _get(f"/person/{tmdb_id}")