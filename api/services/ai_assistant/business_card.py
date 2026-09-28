"""
The business as its customers see it on a sold receptionist's page (``/ia/{slug}`` once delivered).

A business without a website pastes the receptionist's address on its Google profile (« Site web », « Prendre
rendez-vous »), in its voicemail and on a QR code: its customers land on a page that must read as the business's
own. Besides the receptionist, it carries what they came for: the phone, the address, the hours, whether it is open
right now, its Google rating. The card holds only what the receptionist itself may say: with the Google listing
switched off as a source, it keeps the phone set in the dashboard and nothing from the listing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from models.ai_assistant import AiAssistant
from schemas.ai_assistant import AiAssistantOpeningHoursRow, AiAssistantPublicBusiness
from services.ai_assistant.knowledge_sources import SourceToggles
from services.ai_assistant.opening_hours import OpeningHoursCalendar


@dataclass(frozen=True)
class BusinessContact:
    """How the business's customers reach it, as its receptionist may say it (None when unknown)."""

    phone: str | None
    email: str | None
    address: str | None


class AiAssistantBusinessCard:
    """Builds the public card of a sold receptionist's business: phone, address, hours, rating."""

    @classmethod
    def contact_of(cls, assistant: AiAssistant) -> BusinessContact:
        """
        The business's phone, email and address, as its receptionist may give them.

        Args:
            assistant: The assistant.

        Returns:
            The phone set in the dashboard, else the listing's; the email and the address come from the listing, and
            nothing does once the listing is switched off as a source.
        """
        knowledge: dict[str, Any] = assistant.knowledge_json or {}
        dashboard_phone = cls._text(assistant.phone)
        if not SourceToggles.of(knowledge).listing:
            return BusinessContact(phone=dashboard_phone, email=None, address=None)
        identity = knowledge.get("identity") if isinstance(knowledge.get("identity"), dict) else {}
        return BusinessContact(
            phone=dashboard_phone or cls._text(identity.get("phone")),
            email=cls._text(identity.get("email")),
            address=cls._text(identity.get("address")),
        )

    @classmethod
    def of(
        cls,
        assistant: AiAssistant,
        *,
        google_rating: float | None = None,
        google_reviews_count: int | None = None,
        now: datetime | None = None,
    ) -> AiAssistantPublicBusiness:
        """
        The card of an assistant's business, from its dashboard phone and its Google listing.

        Args:
            assistant: A sold assistant.
            google_rating: The listing's rating, when known.
            google_reviews_count: How many reviews the rating counts, when known.
            now: The business's current local time (tests); defaults to its clock.

        Returns:
            The card; only the dashboard phone when the listing is switched off as a source.
        """
        knowledge: dict[str, Any] = assistant.knowledge_json or {}
        contact = cls.contact_of(assistant)
        if not SourceToggles.of(knowledge).listing:
            return AiAssistantPublicBusiness(phone=contact.phone)
        rows = [row for row in knowledge.get("opening_hours") or [] if isinstance(row, dict)]
        moment = now or OpeningHoursCalendar.business_now()
        return AiAssistantPublicBusiness(
            phone=contact.phone,
            address=contact.address,
            opening_hours=cls._hours(rows, today=moment.weekday()),
            is_open_now=OpeningHoursCalendar.is_open_at(rows, moment) if rows else None,
            google_rating=google_rating,
            google_reviews_count=google_reviews_count if google_rating is not None else None,
        )

    @staticmethod
    def _hours(rows: list[dict[str, Any]], *, today: int) -> list[AiAssistantOpeningHoursRow]:
        """The readable rows, the first one naming today flagged (a listing names each weekday once)."""
        hours: list[AiAssistantOpeningHoursRow] = []
        has_flagged_today = False
        for row in rows:
            day = str(row.get("day") or "").strip()
            text = str(row.get("hours") or "").strip()
            if not day or not text:
                continue
            is_today = not has_flagged_today and OpeningHoursCalendar.weekday_of(day) == today
            has_flagged_today = has_flagged_today or is_today
            hours.append(AiAssistantOpeningHoursRow(day=day, hours=text, is_today=is_today))
        return hours

    @staticmethod
    def _text(value: Any) -> str | None:
        """A stored text on one line, or None when empty or not a text."""
        return (" ".join(value.split()) or None) if isinstance(value, str) else None
