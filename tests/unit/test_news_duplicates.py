from datetime import datetime, timedelta

from app.domain.news.duplicates import find_original, parse_headline, same_story

SNL_A = "‘SNL’: Druski Dons Whiteface as Elizabeth Holmes in ‘You Can See Everything’ Parody"
SNL_B = "Druski Does Elizabeth Holmes Whiteface In ‘Dru Can See Everything’ Sketch During ‘SNL’ Debut"


def test_same_story_worded_differently_by_two_sources():
    assert same_story(parse_headline(SNL_A), parse_headline(SNL_B))
    assert same_story(
        parse_headline("'Claymore' Creator Norihiro Yagi Begins New Manga"),
        parse_headline("Claymore's Norihiro Yagi Launches Bartlet Fairy Basslet Manga"),
    )


def test_related_but_different_stories_are_kept():
    stone = parse_headline("Emma Stone Crashes Druski’s ‘SNL’ Monologue in Hilarious Fashion")
    assert not same_story(parse_headline(SNL_B), stone)
    # generic words don't count
    assert not same_story(
        parse_headline("One Piece Season 2 Official Trailer Released"),
        parse_headline("Bleach Season 2 Official Trailer Released"),
    )
    # announcement boilerplate doesn't count
    assert not same_story(
        parse_headline("Hirayasumi Anime Reveals Ending Theme Song Artist"),
        parse_headline("Everyone's Darling Has a Secret Reveals Additional Cast, Ending Theme Song"),
    )
    # a review is not the news item about the same game
    assert not same_story(
        parse_headline("Dragon's Dogma II: Dark Arisen Game Review"),
        parse_headline("Dragon's Dogma 2: Dark Arisen Announces Delicious in Dungeon Collaboration"),
    )
    # too few distinctive words to be sure
    assert not same_story(
        parse_headline("Black Clover Season 2 ‒ Episode 175"),
        parse_headline("Black Clover Season 2 Episode 6 Previews Noelle and Charlotte Facing Vanica"),
    )


def test_only_other_sources_are_merged_and_never_videos():
    recent = [
        ("same_site", "variety", parse_headline(SNL_A)),
        ("other_site", "thr", parse_headline(SNL_A)),
    ]
    snl_b = parse_headline(SNL_B)
    assert find_original(snl_b, "variety", recent) == "other_site"
    assert find_original(snl_b, "boxoffice", recent) == "same_site"  # first match wins
    assert find_original(snl_b, "youtube", recent) is None
    assert find_original(parse_headline("Chainsaw Man Movie Box Office Record"), "variety", recent) is None


def test_close_meaning_merges_when_embeddings_are_available():
    joins = "Emma Stone Joins Druski During His ‘SNL’ Hosting Debut"
    crashes = "Emma Stone Crashes Druski’s ‘SNL’ Monologue in Hilarious Fashion"
    assert not same_story(parse_headline(joins), parse_headline(crashes))  # words alone: 4 of 7
    t = datetime(2026, 11, 7, 23, 0)
    near, far = (1.0, 0.0), (0.8, 0.6)  # cosine 0.8
    assert same_story(parse_headline(joins, near, t), parse_headline(crashes, far, t + timedelta(minutes=7)))
    assert not same_story(parse_headline(joins, (1.0, 0.0), t), parse_headline(crashes, (0.0, 1.0), t))
    # similar follow-ups days apart are separate updates
    assert not same_story(parse_headline(joins, near, t), parse_headline(crashes, far, t + timedelta(days=2)))
    # close meaning but no shared name is never the same story
    assert not same_story(parse_headline("One Piece Wins Award", near, t), parse_headline("Bleach Gets Prize", near, t))
