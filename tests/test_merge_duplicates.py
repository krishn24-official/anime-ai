"""Integration test for app/scripts/merge_duplicates.py (runs on the test database)."""

import json

import pytest

from app.db.mongo import get_db
from app.scripts import merge_duplicates


@pytest.fixture
async def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(merge_duplicates, "BACKUP_DIR", str(tmp_path))
    db = get_db()
    # Like the live data before merging: duplicates exist, so these unique
    # external-id indexes could not be created yet...
    for col in ("characters", "actors", "movies", "tv_series"):
        for name in await db[col].index_information():
            if name.startswith("unique_"):
                await db[col].drop_index(name)
    # ...but voice_actors had no clashing ids, so its index exists. The copy has the
    # AniList id and the original does not (the case that broke the first live run).
    await db.voice_actors.insert_many([
        {"_id": "va_junko_takeuchi", "name": "Junko Takeuchi", "character_ids": [], "is_deleted": False},
        {"_id": "va_junko_takeuchi_1", "name": "Junko Takeuchi", "source_metadata": {"anilist": {"id": 95015}},
         "is_deleted": False},
    ])
    await db.characters.insert_many([
        {"_id": "char_luffy_monkey", "name": "Luffy Monkey", "anime_ids": ["anime_one_piece_film_red"],
         "source_metadata": {"anilist": {"id": 40}}, "is_deleted": False},
        {"_id": "char_luffy_monkey_40", "name": "Luffy Monkey", "anime_ids": ["anime_one_piece"],
         "native_name": "モンキー・D・ルフィ", "source_metadata": {"anilist_id": 40, "anilist": {"id": 40}},
         "is_deleted": False},
        {"_id": "char_zoro", "name": "Zoro", "source_metadata": {"anilist": {"id": 62}}, "is_deleted": False},
        # same name, different AniList id: a different character -> must be kept
        {"_id": "char_kureha", "name": "Kureha", "source_metadata": {"anilist": {"id": 1}}, "is_deleted": False},
        {"_id": "char_kureha_2", "name": "Kureha", "source_metadata": {"anilist": {"id": 2}}, "is_deleted": False},
    ])
    await db.relationships.insert_many([
        {"_id": "rel_a", "source_id": "char_zoro", "target_id": "char_luffy_monkey", "relationship": "friend"},
        {"_id": "rel_b", "source_id": "char_zoro", "target_id": "char_luffy_monkey_40", "relationship": "friend"},
    ])
    await db.events.insert_many([
        {"_id": "event_x", "manga_id": "manga_op", "chapter_number": 1, "event_type": "manga_release",
         "character_ids": ["char_luffy_monkey_40"], "is_deleted": False},
        {"_id": "event_x_copy", "manga_id": "manga_op", "chapter_number": 1, "event_type": "manga_release",
         "is_deleted": False},
    ])
    await db.actors.insert_many([
        {"_id": "actor_a_gurung", "name": "A. Gurung", "tmdb_id": 2395672, "is_deleted": False},
        {"_id": "actor_a_gurung_2", "name": "A. Gurung", "tmdb_id": 2395672, "birthdate": "1990-01-01", "is_deleted": False},
    ])
    await db.movies.insert_many([
        {"_id": "movie_x", "title": "X", "source_metadata": {"tmdb_id": 7}, "is_deleted": False,
         "cast": [{"actor_id": "actor_a_gurung_2", "order": 0}]},
        {"_id": "movie_x_1", "title": "X", "plot": "A plot.", "source_metadata": {"tmdb_id": 7}, "is_deleted": False},
    ])
    await db.tv_series.insert_many([
        {"_id": "tv_loki", "title": "Loki", "year": "2021", "source_metadata": {"imdb_id": "tt9140554"}, "is_deleted": False},
        {"_id": "tv_loki_1", "title": "Loki", "year": "2021", "source_metadata": {"tmdb_id": 84958}, "is_deleted": False},
    ])
    # both copies are trending -> repointing collides with the unique index
    await db.trending.insert_many([
        {"content_type": "movie", "content_id": "movie_x", "score": 1.0, "pinned": False},
        {"content_type": "movie", "content_id": "movie_x_1", "score": 2.0, "pinned": False},
    ])
    return db


async def test_dry_run_changes_nothing(seeded):
    await merge_duplicates.run(apply=False)
    assert await seeded.characters.count_documents({}) == 5
    assert await seeded.actors.count_documents({}) == 2


async def test_apply_merges_and_repoints(seeded, tmp_path):
    db = seeded
    await merge_duplicates.run(apply=True)

    # characters: copy merged into the original; namesakes untouched
    luffy = await db.characters.find_one({"_id": "char_luffy_monkey"})
    assert await db.characters.find_one({"_id": "char_luffy_monkey_40"}) is None
    assert set(luffy["anime_ids"]) == {"anime_one_piece_film_red", "anime_one_piece"}
    assert luffy["native_name"] == "モンキー・D・ルフィ"
    assert luffy["source_metadata"]["anilist_id"] == 40
    assert await db.characters.count_documents({"name": "Kureha"}) == 2

    # references re-pointed; duplicate relationship removed
    rels = await db.relationships.find({}).to_list(None)
    assert [(r["source_id"], r["target_id"]) for r in rels] == [("char_zoro", "char_luffy_monkey")]
    assert await db.events.count_documents({}) == 1
    event = await db.events.find_one({})
    assert event.get("character_ids", ["char_luffy_monkey"]) == ["char_luffy_monkey"]

    # actors: copy's birthdate kept, cast re-pointed
    actor = await db.actors.find_one({"_id": "actor_a_gurung"})
    assert actor["birthdate"] == "1990-01-01"
    assert await db.actors.count_documents({}) == 1
    movie = await db.movies.find_one({"_id": "movie_x"})
    assert movie["cast"][0]["actor_id"] == "actor_a_gurung"
    assert movie["plot"] == "A plot."

    # trending: colliding copy dropped instead of failing
    assert await db.trending.count_documents({"content_id": {"$in": ["movie_x", "movie_x_1"]}}) == 1

    # tv: manual record kept, gains the TMDb id from the copy
    loki = await db.tv_series.find_one({"_id": "tv_loki"})
    assert loki["source_metadata"]["tmdb_id"] == 84958
    assert await db.tv_series.count_documents({}) == 1

    # voice actor: original kept and gains the AniList id despite the unique index
    junko = await db.voice_actors.find_one({"_id": "va_junko_takeuchi"})
    assert junko["source_metadata"]["anilist"]["id"] == 95015
    assert await db.voice_actors.count_documents({}) == 1

    # backup written
    backups = list(tmp_path.glob("duplicate_merge_*.json"))
    assert len(backups) == 1
    content = json.loads(backups[0].read_text(encoding="utf-8"))
    assert "characters" in content["entities"]
