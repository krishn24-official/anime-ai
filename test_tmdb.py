import asyncio
from app.backend.ingestion.tmdb_client import _get

async def main():
    # Trap (2024)
    movie_id = 1032823
    res = await _get(f"/movie/{movie_id}", {"append_to_response": "release_dates"})
    if res:
        print("Top-level release_date:", res.get("release_date"))
        for country in res.get("release_dates", {}).get("results", []):
            if country.get("iso_3166_1") == "US":
                print("US Release Dates:")
                for r in country.get("release_dates", []):
                    print(f"  Type {r.get('type')}: {r.get('release_date')[:10]}")

if __name__ == "__main__":
    asyncio.run(main())
