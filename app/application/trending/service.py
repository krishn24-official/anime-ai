"""Trending use cases: admin pins, the public trending list, and automatic
trending computed from news mentions and search clicks."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Sequence

from app.application.errors import InvalidInputError, NotFoundError
from app.domain.shared.content import (
    ContentRef,
    content_types_label,
    is_valid_content_type,
)
from app.domain.shared.ports import ContentCatalog, ImageStorage
from app.domain.trending import rules
from app.domain.trending.entities import TrendingEntry, TrendingItem, TrendingSource
from app.domain.trending.ports import TrendingRepository, TrendingSignalRepository

logger = logging.getLogger(__name__)

# (alias, content_type, content_id) tuples, as produced by the title matcher.
AliasMatch = tuple[str, str, str]
FindMatches = Callable[[str, Sequence], list[AliasMatch]]


class TrendingService:
    def __init__(
        self,
        entries: TrendingRepository,
        signals: TrendingSignalRepository,
        catalog: ContentCatalog,
        images: ImageStorage,
        find_matches: FindMatches,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._entries = entries
        self._signals = signals
        self._catalog = catalog
        self._images = images
        self._find_matches = find_matches
        self._now = clock

    # ── Admin pins ────────────────────────────────────────────────────────────

    async def pin(
        self,
        content_type: str,
        content_id: str,
        admin_id: str,
        note: str | None = None,
        expires_at: datetime | None = None,
        image_bytes: bytes | None = None,
    ) -> None:
        """Pin catalog content to the top of trending as an Editor's Pick.

        Pinning the same content again replaces its note/expiry/poster.
        """
        if not is_valid_content_type(content_type):
            raise InvalidInputError(
                f"Invalid content type. Must be one of: {content_types_label()}"
            )

        ref = ContentRef(content_type, content_id)
        if ref not in await self._catalog.get_summaries([ref]):
            raise NotFoundError("Content not found")

        custom_poster = None
        if image_bytes:
            custom_poster = await self._images.upload(
                image_bytes, folder=rules.TRENDING_IMAGE_FOLDER
            )

        await self._upsert(
            TrendingEntry(
                content=ref,
                source=TrendingSource.MANUAL.value,
                reason=rules.EDITOR_PICK_REASON,
                score=rules.EDITOR_PICK_SCORE,
                pinned=True,
                computed_at=self._now(),
                set_by=admin_id,
                note=note,
                expires_at=expires_at,
                custom_poster=custom_poster,
            )
        )

    async def unpin(self, content_type: str, content_id: str) -> None:
        await self._entries.delete(ContentRef(content_type, content_id))

    # ── Reading the list ──────────────────────────────────────────────────────

    async def list_trending(self, limit: int = 10) -> list[TrendingItem]:
        entries = await self._entries.list_active(self._now(), limit)
        if not entries:
            return []

        summaries = await self._catalog.get_summaries([e.content for e in entries])

        items = []
        for entry in entries:
            summary = summaries.get(entry.content)
            items.append(
                TrendingItem(
                    content_type=entry.content.content_type,
                    content_id=entry.content.content_id,
                    title=(summary.title if summary else None)
                    or entry.content.content_id,
                    poster_image=entry.custom_poster
                    or (summary.poster_image if summary else None),
                    reason=entry.reason,
                    pinned=entry.pinned,
                    set_at=entry.computed_at,
                    note=entry.note,
                )
            )
        return items

    # ── Signals ───────────────────────────────────────────────────────────────

    async def record_search_click(
        self, content_type: str, content_id: str, query: str, user_id: str
    ) -> None:
        await self._signals.record_search_click(
            ContentRef(content_type, content_id), query, user_id, self._now()
        )

    async def scan_article_for_mentions(
        self, news_id: str, title: str, description: str, alias_index: Sequence
    ) -> None:
        text = f"{title} {description[:2000]}"
        for alias, content_type, content_id in self._find_matches(text, alias_index):
            await self._signals.record_mention(
                ContentRef(content_type, content_id), news_id, alias, self._now()
            )

    # ── Automatic trending ────────────────────────────────────────────────────

    async def recompute_news_trending(self, hours: int = 48) -> dict:
        now = self._now()
        expires = now + timedelta(hours=hours)
        updated = 0

        for item in await self._signals.mention_counts(since=now - timedelta(hours=hours)):
            stored = await self._upsert(
                TrendingEntry(
                    content=item.content,
                    source=TrendingSource.NEWS.value,
                    reason=rules.news_reason(item.mention_count),
                    score=float(item.mention_count),
                    pinned=False,
                    computed_at=now,
                    expires_at=expires,
                )
            )
            updated += stored

        return {"trending_updated": updated}

    async def recompute_search_trending(self, hours: int = 3) -> dict:
        now = self._now()
        counts = await self._signals.search_counts(since=now - timedelta(hours=hours))
        if not counts:
            return {
                "evaluated": 0,
                "qualified": 0,
                "threshold_used": rules.MIN_SEARCH_THRESHOLD,
            }

        threshold = rules.search_qualifying_threshold(counts)
        expires = now + timedelta(hours=hours)
        updated = 0

        for item in counts:
            if item.distinct_searcher_count < threshold:
                continue
            stored = await self._upsert(
                TrendingEntry(
                    content=item.content,
                    source=TrendingSource.SEARCH.value,
                    reason=rules.search_reason(item.distinct_searcher_count),
                    score=float(item.distinct_searcher_count),
                    pinned=False,
                    computed_at=now,
                    expires_at=expires,
                )
            )
            updated += stored

        summary = {
            "evaluated": len(counts),
            "qualified": updated,
            "threshold_used": threshold,
        }
        logger.info("search trending recompute: %s", summary)
        return summary

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _upsert(self, entry: TrendingEntry) -> bool:
        """Save the entry unless it would overwrite an admin pin."""
        existing = None if entry.pinned else await self._entries.get(entry.content)
        if not rules.may_replace(existing, entry):
            return False
        await self._entries.save(entry)
        return True
