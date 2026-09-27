"""
The event intake of the receptionist (weddings, receptions, catering): what she collects before handing over, and
the days already taken in the agenda so she never suggests one. Only the trades that live on events get it.
"""

from __future__ import annotations

import logging
import time as clock
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import ClassVar

from sqlalchemy.orm import Session

from models.ai_assistant import AiAssistant
from models.ai_assistant_calendar import AiAssistantCalendar
from models.prospect_db import ProspectDB
from services.ai_assistant.calendar_access import ai_assistant_calendar_access
from services.ai_assistant.calendar_settings import CalendarSettings
from services.ai_assistant.google_calendar_client import GoogleCalendarError, google_calendar_client
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.french_date_formatter import FrenchDateFormatter

logger = logging.getLogger(__name__)

# Accent-free word starts of the Google categories that live on events (« Salle de réception », « Traiteur »).
EVENT_TRADE_WORDS: tuple[str, ...] = (
    "mariage",
    "wedding",
    "banquet",
    "recept",
    "traiteur",
    "evenement",
    "seminaire",
    "orchestre",
    "photographe",
)
# A day is taken when the agenda is busy this long on it (an all-day event covers it whole).
TAKEN_HOURS = 6
LOOK_AHEAD_DAYS = 365
_CACHE_SECONDS = 900
_MAX_DAYS_IN_PROMPT = 40


@dataclass(frozen=True)
class EventIntakeContext:
    """What the prompt knows for an event trade: the days already taken, and whether the agenda was read."""

    busy_days: tuple[date, ...]
    agenda_known: bool


class AiAssistantEventIntake:
    """Decides whether an assistant takes event requests, and what its prompt says about them."""

    _cache: ClassVar[dict[int, tuple[float, tuple[date, ...]]]] = {}

    @staticmethod
    def is_event_trade(category: str | None) -> bool:
        """
        Whether a Google category lives on events (weddings, receptions, catering, seminars).

        Args:
            category: The business's Google Maps category, or None.

        Returns:
            True for an event trade.
        """
        folded = unicodedata.normalize("NFKD", (category or "").lower()).encode("ascii", "ignore").decode()
        words = [word for word in folded.replace("-", " ").split() if word]
        return any(word.startswith(start) for word in words for start in EVENT_TRADE_WORDS)

    @classmethod
    async def context(cls, db: Session, assistant: AiAssistant) -> EventIntakeContext | None:
        """
        What the prompt needs for an event trade: the taken days of its agenda when it is connected.

        Args:
            db: Active database session.
            assistant: The assistant answering.

        Returns:
            The context, or None when the business does not live on events.
        """
        category = (
            db.query(ProspectDB.category).filter(ProspectDB.id == assistant.prospect_id).scalar()
            if assistant.prospect_id is not None
            else None
        )
        if not cls.is_event_trade(category):
            return None
        calendar = ai_assistant_calendar_access.usable_calendar(db, assistant)
        if calendar is None:
            return EventIntakeContext(busy_days=(), agenda_known=False)
        try:
            return EventIntakeContext(busy_days=await cls.busy_days(db, calendar), agenda_known=True)
        except GoogleCalendarError:
            logger.warning("Event intake of assistant %s: the agenda could not be read", assistant.id, exc_info=True)
            return EventIntakeContext(busy_days=(), agenda_known=False)

    @classmethod
    async def busy_days(
        cls, db: Session, calendar: AiAssistantCalendar, *, now: datetime | None = None
    ) -> tuple[date, ...]:
        """
        The days already taken over the next year, in business time, cached a quarter of an hour per agenda.

        Args:
            db: Active database session.
            calendar: The connected agenda.
            now: Current business time, aware (tests); defaults to now.

        Returns:
            The taken days, sorted.

        Raises:
            GoogleCalendarError: When the agenda cannot be read.
        """
        cached = cls._cache.get(calendar.id)
        if cached is not None and clock.monotonic() - cached[0] < _CACHE_SECONDS:
            return cached[1]
        local_now = OpeningHoursCalendar.localize(now or OpeningHoursCalendar.business_now())
        start = OpeningHoursCalendar.to_utc(local_now)
        end = start + timedelta(days=LOOK_AHEAD_DAYS)
        calendar_id = CalendarSettings.of(calendar).calendar_id
        periods = await ai_assistant_calendar_access.with_fresh_token(
            db,
            calendar,
            lambda token: google_calendar_client.busy_periods(token, calendar_id, start=start, end=end),
        )
        days = cls.taken_days((period.start, period.end) for period in periods)
        cls._cache[calendar.id] = (clock.monotonic(), days)
        return days

    @staticmethod
    def taken_days(periods: object) -> tuple[date, ...]:
        """
        The business days a set of busy periods (naive UTC) takes: those busy ``TAKEN_HOURS`` or more.

        Args:
            periods: ``(start, end)`` pairs, naive UTC.

        Returns:
            The taken days, sorted.
        """
        hours: dict[date, float] = {}
        for start_utc, end_utc in periods:  # type: ignore[union-attr]
            cursor = OpeningHoursCalendar.to_business_time(start_utc)
            local_end = OpeningHoursCalendar.to_business_time(end_utc)
            while cursor < local_end:
                next_day = datetime.combine(cursor.date() + timedelta(days=1), time.min, tzinfo=cursor.tzinfo)
                chunk_end = min(local_end, next_day)
                hours[cursor.date()] = hours.get(cursor.date(), 0.0) + (chunk_end - cursor).total_seconds() / 3600
                cursor = chunk_end
        return tuple(sorted(day for day, busy in hours.items() if busy >= TAKEN_HOURS))

    @staticmethod
    def prompt_lines(context: EventIntakeContext) -> list[str]:
        """
        The prompt block of an event trade: what to collect, and the taken days when the agenda is known.

        Args:
            context: The event context.

        Returns:
            The lines to add to the system prompt.
        """
        lines = [
            "ÉVÉNEMENT : quand un visiteur parle d'un événement (mariage, réception, repas de groupe, prestation "
            "traiteur), prépare sa demande pour que l'entreprise rappelle avec une proposition. Il faut quatre "
            "informations : la date (ou la période), le lieu (chez l'entreprise, chez le client, ailleurs), le nombre "
            "d'invités, le budget approximatif. Tant qu'il en manque une, demande-la, UNE question à la fois, AVANT "
            "de parler de rappel ou de coordonnées (s'il ne sait pas, passe à la suivante). Quand tu les as, résume en "
            "une phrase (« un mariage le samedi 12 juin 2027, 80 invités, chez vous, autour de 8 000 € ») puis "
            "demande le prénom et un téléphone ou un e-mail. Tu ne confirmes jamais une réservation ni un prix."
        ]
        if not context.agenda_known:
            lines.append(
                "Tu ne vois pas l'agenda : ne dis jamais qu'une date est libre ou prise ; dis que tu la notes et que "
                "l'entreprise la confirme au rappel."
            )
            return lines
        if context.busy_days:
            shown = context.busy_days[:_MAX_DAYS_IN_PROMPT]
            labels = ", ".join(f"{FrenchDateFormatter.short_date(day)}/{day.year}" for day in shown)
            more = "…" if len(context.busy_days) > len(shown) else ""
            lines.append(
                "DATES DÉJÀ PRISES DANS L'AGENDA (n'en propose jamais une ; si le visiteur en donne une, dis qu'elle "
                f"est prise et demande une autre date) : {labels}{more}."
            )
        lines.append(
            "Toute autre date n'est pas prise à ce jour : dis-le simplement, en précisant que l'entreprise confirme "
            "au rappel."
        )
        return lines


ai_assistant_event_intake = AiAssistantEventIntake()
