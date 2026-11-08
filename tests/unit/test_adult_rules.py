from app.domain.media.adult import MAINSTREAM_MIN_VOTES, is_adult_tmdb, tmdb_keyword_ids

SOFTCORE, PINK, DRAMA = 155477, 159551, 9999


def test_flagged_or_tagged_low_profile_titles_are_adult():
    assert is_adult_tmdb(True, [], 5000)  # TMDb adult flag always wins
    assert is_adult_tmdb(False, [SOFTCORE], 12)
    assert is_adult_tmdb(False, [DRAMA, PINK], 0)


def test_famous_tagged_films_and_untagged_titles_are_kept():
    assert not is_adult_tmdb(False, [SOFTCORE], MAINSTREAM_MIN_VOTES)  # e.g. Antichrist
    assert not is_adult_tmdb(False, [DRAMA], 3)


def test_keyword_ids_from_movie_and_tv_payloads():
    assert tmdb_keyword_ids({"keywords": {"keywords": [{"id": 1}, {"id": 2}]}}) == [1, 2]
    assert tmdb_keyword_ids({"keywords": {"results": [{"id": 3}]}}) == [3]
    assert tmdb_keyword_ids({}) == []
