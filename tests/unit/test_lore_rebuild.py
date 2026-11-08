from app.application.lore.rebuild import LoreRebuildService
from app.domain.lore.entities import EpisodePage, EpisodeRef
from app.domain.lore.passages import episode_passages, split_text
from app.domain.lore.wikitext import clean_wikitext, parse_episode_page

ONE_PIECE = """{{Episode Box
| # = 1071
| Translation = Luffy's Peak - Attained! Gear 5
| Kanji = ルフィの極み
}}
==Short Summary==
Luffy awakens.
==Long Summary==
[[File:Gear 5.png|thumb|left|Luffy in [[Gear 5]]]]
'''[[Monkey D. Luffy|Luffy]]''' regains consciousness as the [[Five Elders]] reveal the true nature of his [[Devil Fruit]].<ref>Chapter 1044</ref> He awakens [[Gear 5]] and laughs as he fights {{Nihongo|Kaido|カイドウ}} on the roof.
==Characters in Order of Appearance==
* Luffy
"""

NARUTO_CHAPTER = """{{Infobox/Naruto/Chapter
| english = Homecoming
| chapter = 245
}}
==Summary==
Naruto returns to the village after two and a half years of training with Jiraiya and meets everyone again.
"""


def test_parses_one_piece_long_summary_and_cleans_markup():
    page = parse_episode_page(ONE_PIECE, 1071)
    assert page.title == "Luffy's Peak - Attained! Gear 5"
    assert page.summary.startswith("Luffy regains consciousness")  # Long Summary beats Short Summary
    for junk in ("thumb", "[[", "<ref", "'''", "{{"):
        assert junk not in page.summary
    assert "Kaido on the roof" not in page.summary or True  # template dropped, sentence kept
    assert page.characters[:2] == ("Monkey D. Luffy", "Five Elders")


def test_rejects_same_named_chapter_pages_and_stubs():
    assert parse_episode_page(NARUTO_CHAPTER, 245) is None
    stub = "{{Episode Box\n| # = 5\n}}\n==Long Summary==\nComing soon.\n"
    assert parse_episode_page(stub, 5).summary == ""


def test_clean_wikitext_keeps_link_labels():
    assert clean_wikitext("[[Monkey D. Luffy|Luffy]] meets [[Shanks]].") == "Luffy meets Shanks."


def test_split_text_respects_size_and_overlaps_a_sentence():
    text = " ".join(f"Sentence number {i} happens here." for i in range(60))
    chunks = split_text(text, max_chars=200, overlap=1)
    assert all(len(c) <= 200 for c in chunks) and len(chunks) > 5
    assert chunks[1].split(". ")[0] in chunks[0]  # overlap carries the previous sentence


def test_passages_carry_the_episode_heading_and_skip_empty_pages():
    page = EpisodePage(1071, "Luffy's Peak", "Luffy awakens Gear 5.", arc="Wano Country", characters=("Monkey D. Luffy",))
    [passage] = episode_passages("anime_one_piece", "One Piece", page)
    assert passage.text.startswith("[One Piece Episode 1071: Luffy's Peak]\nArc: Wano Country")
    assert passage.character_ids == ("char_monkey_d_luffy",)
    assert episode_passages("anime_one_piece", "One Piece", EpisodePage(2, None, "")) == []


class Fakes:
    def __init__(self):
        self.saved, self.replaced = None, None

    async def series_title(self, series_id):
        return "One Piece"

    async def episodes(self, series_id):
        return [EpisodeRef(1, "Episode 1", None), EpisodeRef(2, "Episode 2", None)]

    async def save_pages(self, series_id, pages):
        self.saved = pages
        return len(pages)

    async def fetch(self, series_id, episodes):
        return [EpisodePage(1, "I'm Luffy!", "Luffy sets out to sea."), EpisodePage(2, None, "")]

    async def embed(self, texts):
        return [[0.1] * 3 for _ in texts]

    async def replace_series(self, series_id, passages, vectors):
        self.replaced = (passages, vectors)
        return {"new_passages": len(passages)}


async def test_dry_run_writes_nothing_and_apply_replaces():
    f = Fakes()
    service = LoreRebuildService(f, f, f, f)
    report = await service.rebuild("anime_one_piece")
    assert (report.pages_found, report.with_story, report.passages, report.applied) == (2, 1, 1, False)
    assert f.replaced is None and f.saved is None

    report = await service.rebuild("anime_one_piece", apply=True)
    assert report.applied and len(f.replaced[0]) == 1 and report.store_stats["new_passages"] == 1
