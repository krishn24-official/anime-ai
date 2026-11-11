"""Unit tests for video rules and the TMDb refresh decisions (no database, no network)."""

from datetime import datetime, timezone

from app.domain.media import videos as v
from app.services.tmdb_video_refresh_service import build_updates


def tmdb(key, type_, official=True, published="2026-01-01T00:00:00.000Z", lang="en", site="YouTube", name=None):
    return {"key": key, "type": type_, "official": official, "published_at": published,
            "iso_639_1": lang, "site": site, "name": name or f"{type_} {key}"}


def test_trailers_first_extras_separate_and_capped():
    results = [tmdb("c1", "Clip"), tmdb("f1", "Featurette"), tmdb("t1", "Trailer"), tmdb("z1", "Teaser")]
    results += [tmdb(f"x{i}", "Clip") for i in range(20)]
    trailers, extras = v.organize_tmdb_videos(results)
    assert [t["type"] for t in trailers] == ["Trailer", "Teaser"]
    assert all(e["type"] not in v.TRAILER_TYPES for e in extras)
    assert len(extras) == v.MAX_EXTRAS


def test_best_trailer_official_then_newest_then_language():
    results = [
        tmdb("old", "Trailer", published="2025-01-01T00:00:00Z"),
        tmdb("new", "Trailer", published="2026-06-01T00:00:00Z"),
        tmdb("fan", "Trailer", official=False, published="2026-09-01T00:00:00Z"),
        tmdb("ja", "Trailer", lang="ja", published="2026-10-01T00:00:00Z"),
        tmdb("vimeo", "Trailer", site="Vimeo"),
        tmdb("new", "Trailer"),  # duplicate key
    ]
    trailers, _ = v.organize_tmdb_videos(results, ("en", "ja"))
    assert [t["url"][-3:] for t in trailers] == ["new", "old", "fan", "=ja"]
    assert trailers[0]["url"] == "https://www.youtube.com/watch?v=new"


def test_original_language_used_when_no_english_trailer():
    trailers, _ = v.organize_tmdb_videos([tmdb("ja1", "Trailer", lang="ja")], ("en", "ja"))
    assert trailers and trailers[0]["language"] == "ja"


def test_split_legacy_list_and_detect_manual():
    legacy = [{"url": "u1", "label": "Clip"}, {"url": "u2", "label": "Teaser"}, {"url": "u3", "label": "Trailer"},
              {"url": "u4", "label": "Featurette"}]
    trailers, extras = v.split_stored_videos(legacy)
    assert [t["url"] for t in trailers] == ["u3", "u2"]
    assert [e["url"] for e in extras] == ["u1", "u4"]
    assert not v.has_manual_trailers(legacy)
    assert v.has_manual_trailers([{"url": "u", "label": "Ramayana Official Trailer"}])
    assert not v.has_manual_trailers([{"url": "u", "label": "Official Trailer", "type": "Trailer"}])


NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)
DETAILS = {
    "id": 1, "status": "Post Production", "original_language": "en",
    "poster_path": "/new.jpg", "backdrop_path": "/bd.jpg",
    "release_date": "2027-05-01", "videos": {"results": [tmdb("t1", "Trailer")]},
}


def test_refresh_adds_trailer_and_shifts_upcoming_date():
    doc = {"trailers": [], "images": {"poster": "https://image.tmdb.org/t/p/w500/old.jpg"}, "release_date": "2026-12-18"}
    u = build_updates("movie", doc, DETAILS, NOW)
    assert u["trailers"][0]["url"].endswith("t1")
    assert u["release_date"] == "2027-05-01" and u["year"] == "2027"
    assert u["images.poster"].endswith("/new.jpg")
    assert u["status"] == "Post Production"


def test_refresh_keeps_manual_trailers_uploaded_images_and_released_dates():
    doc = {
        "trailers": [{"url": "https://youtu.be/x", "label": "My trailer"}],
        "images": {"poster": "https://res.cloudinary.com/demo/poster.jpg"},
        "release_date": "2020-01-01",
    }
    u = build_updates("movie", doc, DETAILS, NOW)
    assert u["trailers_manual"] is True and "trailers" not in u
    assert "images.poster" not in u
    assert "release_date" not in u


def test_real_trailer_beats_spots_and_special_looks():
    results = [
        tmdb("look", "Trailer", name="Special Look", published="2026-09-01T00:00:00Z"),
        tmdb("spot", "Trailer", name="TV Spot #9", published="2026-08-01T00:00:00Z"),
        tmdb("off", "Trailer", name="Official Trailer", published="2026-01-01T00:00:00Z"),
        tmdb("tr2", "Trailer", name="Trailer 2", published="2026-03-01T00:00:00Z"),
    ]
    trailers, _ = v.organize_tmdb_videos(results)
    assert [t["url"].split("=")[1] for t in trailers] == ["off", "tr2", "look", "spot"]
