"""Integration test for adult_content_service.remove() on the test database."""

from app.db.mongo import get_db
from app.services.adult_content_service import remove


async def test_remove_soft_deletes_and_cleans_references(tmp_path):
    db = get_db()
    await db.movies.insert_one({"_id": "movie_x", "title": "X", "is_deleted": False, "source_metadata": {"tmdb_id": 1}})
    await db.anime.insert_many([
        {"_id": "anime_bad", "title": {"english": "Bad"}, "is_deleted": False},
        {"_id": "anime_ok", "title": {"english": "Ok"}, "is_deleted": False},
    ])
    await db.characters.insert_many([
        {"_id": "char_only_bad", "name": "A", "anime_ids": ["anime_bad"], "manga_ids": [], "is_deleted": False},
        {"_id": "char_shared", "name": "B", "anime_ids": ["anime_bad", "anime_ok"], "manga_ids": [], "is_deleted": False},
    ])
    await db.relationships.insert_one({"_id": "rel_1", "source_id": "char_only_bad", "target_id": "char_shared", "relationship": "friend"})
    await db.events.insert_one({"_id": "ev_1", "anime_id": "anime_bad", "is_deleted": False})
    await db.trending.insert_one({"content_type": "movie", "content_id": "movie_x", "score": 1.0, "pinned": False})
    await db.watchlist.insert_one({"user_id": "u", "content_type": "anime", "content_id": "anime_bad"})

    stats = await remove(
        {"movies": [{"id": "movie_x", "title": "X", "reason": ["softcore"]}],
         "tv_series": [], "manga": [],
         "anime": [{"id": "anime_bad", "title": "Bad", "reason": ["anilist isAdult"]}]},
        backup_dir=str(tmp_path),
    )

    movie = await db.movies.find_one({"_id": "movie_x"})
    assert movie["is_deleted"] and movie["is_adult"]  # soft delete keeps the id: never re-imported
    assert movie["source_metadata"]["tmdb_id"] == 1
    assert (await db.anime.find_one({"_id": "anime_ok"}))["is_deleted"] is False
    assert await db.trending.count_documents({}) == 0
    assert await db.watchlist.count_documents({}) == 0
    assert (await db.events.find_one({"_id": "ev_1"}))["is_deleted"] is True
    assert (await db.characters.find_one({"_id": "char_only_bad"}))["is_deleted"] is True
    shared = await db.characters.find_one({"_id": "char_shared"})
    assert shared["is_deleted"] is False and shared["anime_ids"] == ["anime_ok"]
    assert await db.relationships.count_documents({}) == 0
    assert stats["backup"] and list(tmp_path.glob("adult_removal_*.json"))
