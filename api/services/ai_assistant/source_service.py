"""
The knowledge sources of an assistant: the business's website (re-read every week or on demand), its Google
listing, and the documents it gave. Each can be turned off; the assistant then stops reading it.

A re-crawl compares the new pages with the stored ones by address (``website_sync``). A site that cannot be read
keeps its previous pages: a broken site never empties the assistant's knowledge.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from core.database import SessionLocal
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.website_sync import AiAssistantWebsiteSync

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Current time, naive UTC (patched in tests)."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class SourceToggles:
    """Which sources the assistant reads: the website pages, the Google listing (the documents have their own)."""

    site: bool
    listing: bool


class AiAssistantSourceService:
    """Reads, compares and switches an assistant's knowledge sources."""

    RECRAWL_EVERY: ClassVar[timedelta] = timedelta(days=7)
    # Assistants re-read per pass (one after the other): the weekly work spreads over the hourly passes.
    MAX_PER_PASS: ClassVar[int] = 10

    @staticmethod
    def toggles(assistant: AiAssistant) -> SourceToggles:
        """
        The sources an assistant reads.

        Args:
            assistant: The assistant.

        Returns:
            Its toggles; a source never switched off is on.
        """
        stored = (assistant.knowledge_json or {}).get("sources")
        stored = stored if isinstance(stored, dict) else {}
        return SourceToggles(site=stored.get("site") is not False, listing=stored.get("listing") is not False)

    @staticmethod
    def set_toggles(db: Session, assistant: AiAssistant, *, site: bool | None, listing: bool | None) -> AiAssistant:
        """
        Switch the website or the Google listing on or off.

        Args:
            db: Active database session.
            assistant: The assistant.
            site: Read the website pages (None keeps it).
            listing: Read the Google listing: hours, rating, services, reviews, address and phone (None keeps it).

        Returns:
            The updated assistant.
        """
        knowledge = dict(assistant.knowledge_json or {})
        current = AiAssistantSourceService.toggles(assistant)
        knowledge["sources"] = {
            "site": current.site if site is None else site,
            "listing": current.listing if listing is None else listing,
        }
        assistant.knowledge_json = knowledge
        db.commit()
        db.refresh(assistant)
        return assistant

    async def refresh_website(self, db: Session, assistant: AiAssistant, *, force: bool = False) -> dict[str, Any]:
        """
        Read the business's website again and keep what changed.

        Args:
            db: Active database session.
            assistant: The assistant (its prospect holds the website address).
            force: Take the read even when it lost more than half of the pages or of the text (« Mettre à jour »);
                the weekly re-read keeps the previous pages then.

        Returns:
            The sync record stored in ``knowledge_json['website_sync']``: when, how many pages, what changed, or
            why the site could not be read (its previous pages are then kept).
        """
        prospect = db.get(ProspectDB, assistant.prospect_id) if assistant.prospect_id else None
        crawl = await ai_assistant_service.crawl_prospect_website(prospect) if prospect is not None else None
        # The read takes seconds: take the assistant as it is now, so a change made meanwhile (a document) stays.
        db.commit()
        db.refresh(assistant)
        knowledge = dict(assistant.knowledge_json or {})
        previous = knowledge.get("website") if isinstance(knowledge.get("website"), dict) else None
        if crawl is not None and not force and AiAssistantWebsiteSync.shrank(previous, crawl):
            sync = AiAssistantWebsiteSync.incomplete(previous, at=_utc_now())
        else:
            sync = AiAssistantWebsiteSync.record(previous, crawl, at=_utc_now())
            if crawl is not None:
                knowledge["website"] = crawl
        knowledge["website_sync"] = sync
        assistant.knowledge_json = knowledge
        db.commit()
        db.refresh(assistant)
        return sync

    def due(self, db: Session, *, now: datetime | None = None) -> list[AiAssistant]:
        """
        The sold assistants whose website was last read a week ago or more (or never), oldest first.

        Args:
            db: Active database session.
            now: Current time, naive UTC (tests); defaults to now.

        Returns:
            At most ``MAX_PER_PASS`` assistants.
        """
        current = now or _utc_now()
        candidates = (
            db.query(AiAssistant)
            .join(ProspectDB, ProspectDB.id == AiAssistant.prospect_id)
            .filter(
                AiAssistant.status == AiAssistantStatus.DELIVERED.value,
                AiAssistant.deleted_at.is_(None),
                ProspectDB.website.isnot(None),
                ProspectDB.website != "",
            )
            .order_by(AiAssistant.id.asc())
            .all()
        )
        due: list[tuple[datetime, AiAssistant]] = []
        for assistant in candidates:
            last = self._last_read(assistant)
            if last is None or current - last >= self.RECRAWL_EVERY:
                due.append((last or datetime.min, assistant))
        due.sort(key=lambda item: item[0])
        return [assistant for _last, assistant in due[: self.MAX_PER_PASS]]

    async def run_pass(self) -> int:
        """
        Re-read the websites that are due, on a fresh session; never raises.

        Returns:
            How many websites were read.
        """
        db = SessionLocal()
        refreshed = 0
        try:
            for assistant in self.due(db):
                try:
                    await self.refresh_website(db, assistant)
                    refreshed += 1
                except Exception:
                    logger.exception("Weekly website read of assistant %s failed", assistant.id)
                    db.rollback()
        except Exception:
            logger.exception("Weekly website read pass failed")
            db.rollback()
        finally:
            db.close()
        return refreshed

    async def run_loop(self, interval_seconds: int = 3600) -> None:
        """
        Every hour, re-read the websites last read a week ago or more.

        Args:
            interval_seconds: Delay between passes.
        """
        while True:
            await self.run_pass()
            await asyncio.sleep(interval_seconds)

    @staticmethod
    def _last_read(assistant: AiAssistant) -> datetime | None:
        """When the website was last read: the last sync, else the crawl stored at creation, naive UTC."""
        knowledge = assistant.knowledge_json or {}
        sync = knowledge.get("website_sync") if isinstance(knowledge.get("website_sync"), dict) else {}
        website = knowledge.get("website") if isinstance(knowledge.get("website"), dict) else {}
        for value in (sync.get("at"), website.get("crawled_at")):
            if isinstance(value, str):
                try:
                    moment = datetime.fromisoformat(value)
                except ValueError:
                    continue
                return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment
        return None


ai_assistant_source_service = AiAssistantSourceService()
