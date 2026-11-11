"""EpisodePageSource backed by fandom wikis (MediaWiki API)."""

import asyncio
import html as html_lib
from dataclasses import replace
import logging
import re
import urllib.parse

import httpx

from app.domain.lore.entities import EpisodePage, EpisodeRef
from app.domain.lore.wikitext import parse_episode_page

logger = logging.getLogger(__name__)

# series -> (wiki host, episode list table on the Naruto wiki's "List of Animated Media" page)
WIKIS: dict[str, tuple[str, int | None]] = {
    "anime_one_piece": ("onepiece.fandom.com", None),
    "anime_bleach": ("bleach.fandom.com", None),
    "anime_attack_on_titan": ("attackontitan.fandom.com", None),
    "anime_demon_slayer": ("kimetsu-no-yaiba.fandom.com", None),
    "anime_jujutsu_kaisen": ("jujutsu-kaisen.fandom.com", None),
    "anime_naruto": ("naruto.fandom.com", 0),
    "anime_naruto_shippuden": ("naruto.fandom.com", 1),
    "anime_boruto": ("naruto.fandom.com", 2),
}
USER_AGENT = "AnimeAI-LoreBot/1.0 (personal, non-commercial project)"
CONCURRENCY = 4  # be polite to fandom


class FandomEpisodeSource:
    def __init__(self, concurrency: int = CONCURRENCY):
        self._sem = asyncio.Semaphore(concurrency)

    async def _get(self, http: httpx.AsyncClient, host: str, params: dict) -> dict:
        for attempt in range(4):
            try:
                async with self._sem:
                    r = await http.get(f"https://{host}/api.php", params={**params, "format": "json"})
                if r.status_code == 200:
                    return r.json()
                if r.status_code not in (429, 500, 502, 503, 504):
                    return {}
            except httpx.HTTPError:
                pass
            await asyncio.sleep(2 * (attempt + 1))
        return {}

    async def _wikitext(self, http, host: str, page: str) -> str:
        data = await self._get(http, host, {"action": "parse", "page": page, "prop": "wikitext", "redirects": 1})
        return ((data.get("parse") or {}).get("wikitext") or {}).get("*", "")

    async def _naruto_list(self, http, table_index: int) -> dict[int, str]:
        """Episode number -> page name, from the Naruto wiki's master episode tables."""
        data = await self._get(http, "naruto.fandom.com", {"action": "parse", "page": "List_of_Animated_Media", "prop": "text"})
        html = ((data.get("parse") or {}).get("text") or {}).get("*", "")
        tables = re.findall(r"<table.*?</table>", html, re.S)
        if table_index >= len(tables):
            return {}
        pages = {}
        for row in re.findall(r"<tr.*?</tr>", tables[table_index], re.S)[1:]:
            first_cell = re.search(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
            link = re.search(r'href="/wiki/([^"#?]+)"', row)
            number = re.sub(r"\D", "", re.sub(r"<[^>]+>", "", first_cell.group(1))) if first_cell else ""
            if number and link:
                pages[int(number)] = html_lib.unescape(urllib.parse.unquote(link.group(1))).replace("_", " ")
        return pages

    async def fetch(self, series_id: str, episodes: list[EpisodeRef]) -> list[EpisodePage]:
        if series_id not in WIKIS:
            raise ValueError(f"No wiki configured for {series_id}; add it to WIKIS")
        host, table = WIKIS[series_id]
        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as http:
            listed = await self._naruto_list(http, table) if table is not None else {}

            async def one(ref: EpisodeRef) -> EpisodePage | None:
                candidates = [ref.page, listed.get(ref.number), ref.title, f"{ref.title} (episode)" if ref.title else None]
                for page in dict.fromkeys(c for c in candidates if c):
                    parsed = parse_episode_page(await self._wikitext(http, host, page), ref.number)
                    if parsed:  # skips same-named chapter/character pages
                        # Some infoboxes say title = {{PAGENAME}}: the page name is the title.
                        named = page if not re.fullmatch(r"episode\s*\d+", page, re.I) else None
                        return replace(parsed, title=parsed.title or named or ref.title)
                return None

            results = await asyncio.gather(*(one(e) for e in episodes))
        found = [p for p in results if p]
        logger.info("%s: %d/%d episode pages found", series_id, len(found), len(episodes))
        return found
