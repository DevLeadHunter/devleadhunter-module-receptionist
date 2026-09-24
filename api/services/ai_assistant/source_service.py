"""
The knowledge sources of an assistant: the business's website (re-read every week or on demand), its Google
listing, and the documents it gave. Each can be turned off; the assistant then stops reading it.

A re-crawl compares the new pages with the stored ones by address (``website_sync``). A site that cannot be read
keeps its previous pages: a broken site never empties the assistant's knowledge.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from core.database import SessionLocal
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.knowledge_builder import SourceToggles
from services.ai_assistant.website_sync import AiAssistantWebsiteSync

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Current time, naive UTC (patched in tests)."""
    return datetime.now(UTC).replace(tzinfo=None)


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
        return SourceToggles.of(assistant.knowledge_json)

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

    @classmethod
    def listing_facts(cls, knowledge: dict[str, Any]) -> list[str]:
        """
        What the Google listing, and the site prepared from it, brings the assistant, in a few French words.

        Args:
            knowledge: The assistant's ``knowledge_json``.

        Returns:
            One short line per fact (« Note 4,6/5 (128 avis) », « Horaires », « 3 services »…).
        """
        facts: list[str] = []
        rating = knowledge.get("rating") if isinstance(knowledge.get("rating"), dict) else {}
        if rating.get("value"):  # Stored as shown: « 4,6/5 », « 128 ».
            count = f" ({rating['count']} avis)" if rating.get("count") else ""
            facts.append(f"Note {rating['value']}{count}")
        if knowledge.get("opening_hours"):
            facts.append("Horaires")
        services = knowledge.get("services") or []
        if services:
            facts.append(cls._count_label(len(services), "service"))
        reviews = knowledge.get("reviews") or []
        if reviews:
            facts.append(f"{len(reviews)} avis client{'s' if len(reviews) > 1 else ''}")
        identity = knowledge.get("identity") if isinstance(knowledge.get("identity"), dict) else {}
        contact = [label for key, label in (("phone", "téléphone"), ("address", "adresse")) if identity.get(key)]
        if contact:
            facts.append(" et ".join(contact).capitalize())
        generated = knowledge.get("generated_site") if isinstance(knowledge.get("generated_site"), dict) else {}
        prepared = [
            part
            for part in (
                "présentation" if generated.get("about") else "",
                cls._count_label(len(generated.get("services") or []), "prestation")
                if generated.get("services")
                else "",
                cls._count_label(len(generated.get("faq") or []), "question fréquente") if generated.get("faq") else "",
            )
            if part
        ]
        if prepared:
            facts.append("Site préparé : " + ", ".join(prepared))
        return facts

    @staticmethod
    def website_url(db: Session, assistant: AiAssistant) -> str | None:
        """
        The site the assistant reads, else its prospect's site never read yet (« Mettre à jour » reads it).

        Args:
            db: Active database session.
            assistant: The assistant.

        Returns:
            The absolute address, or None when there is no readable site.
        """
        knowledge = assistant.knowledge_json or {}
        website = knowledge.get("website") if isinstance(knowledge.get("website"), dict) else {}
        if isinstance(website.get("url"), str) and website["url"]:
            return website["url"]
        prospect = db.get(ProspectDB, assistant.prospect_id) if assistant.prospect_id else None
        if prospect is None or not ai_assistant_service.has_readable_website(prospect):
            return None
        address = (prospect.website or "").strip()
        return address if address.startswith(("http://", "https://")) else f"https://{address}"

    @staticmethod
    def _count_label(count: int, words: str) -> str:
        """« 1 prestation », « 3 questions fréquentes »: every word of ``words`` takes the plural above one."""
        if count <= 1:
            return f"{count} {words}"
        return f"{count} " + " ".join(f"{word}s" for word in words.split())

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
