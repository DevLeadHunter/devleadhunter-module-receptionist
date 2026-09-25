"""
The access to a client's Google agenda: its row, a fresh access token, its busy periods, and what went wrong.

The tokens are stored encrypted; the access token is refreshed (and saved at once) two minutes before it expires.
A lost access puts the agenda in error, and the widget falls back on the wished half-days.
"""

from __future__ import annotations

import logging
import time as clock
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import ClassVar, TypeVar

from sqlalchemy.orm import Session

from enums.ai_assistant_status import AiAssistantStatus
from enums.assistant_calendar_status import AssistantCalendarStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_calendar import AiAssistantCalendar
from services.activity_log_service import CATEGORY_ASSISTANT, STATUS_WARNING, activity_log_service
from services.ai_assistant.calendar_settings import CalendarSettings
from services.ai_assistant.calendar_slot_grid import AiAssistantCalendarSlotGrid
from services.ai_assistant.google_calendar_client import BusyPeriod, GoogleCalendarError, google_calendar_client
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.encryption_service import encryption_service

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AiAssistantCalendarAccess:
    """Reads a sold assistant's agenda at Google with its stored tokens, and records its failures."""

    BUSY_CACHE_SECONDS: ClassVar[float] = 60.0

    def __init__(self) -> None:
        # Busy periods per agenda, for a minute: the widget's slot page is not a Google call per visitor click.
        self._busy_cache: dict[int, tuple[float, list[BusyPeriod]]] = {}

    @staticmethod
    def calendar_of(db: Session, assistant: AiAssistant) -> AiAssistantCalendar | None:
        """The agenda row of an assistant, connected or in error."""
        return db.query(AiAssistantCalendar).filter(AiAssistantCalendar.assistant_id == assistant.id).first()

    def usable_calendar(self, db: Session, assistant: AiAssistant) -> AiAssistantCalendar | None:
        """
        The agenda the widget books into, when there is one.

        Args:
            db: Active database session.
            assistant: The assistant.

        Returns:
            The connected agenda of a sold assistant (never a demo's), or None.
        """
        if assistant.status != AiAssistantStatus.DELIVERED.value or not google_calendar_client.is_configured:
            return None
        calendar = self.calendar_of(db, assistant)
        if calendar is None or calendar.status != AssistantCalendarStatus.CONNECTED.value:
            return None
        return calendar

    async def busy_periods(self, db: Session, calendar: AiAssistantCalendar, local_now: datetime) -> list[BusyPeriod]:
        """
        The agenda's busy periods over the offer window, cached a minute per agenda.

        Args:
            db: Active database session.
            calendar: The connected agenda.
            local_now: Current business time, aware.

        Returns:
            The busy periods, naive UTC.

        Raises:
            GoogleCalendarError: When the agenda cannot be read (the failure is recorded first).
        """
        cached = self._busy_cache.get(calendar.id)
        if cached is not None and clock.monotonic() - cached[0] < self.BUSY_CACHE_SECONDS:
            return cached[1]
        start = OpeningHoursCalendar.to_utc(local_now)
        end = start + timedelta(days=AiAssistantCalendarSlotGrid.LOOK_AHEAD_DAYS + 1)
        calendar_id = CalendarSettings.of(calendar).calendar_id
        try:
            busy = await self.with_fresh_token(
                db,
                calendar,
                lambda token: google_calendar_client.busy_periods(token, calendar_id, start=start, end=end),
            )
        except GoogleCalendarError as exc:
            assistant = db.query(AiAssistant).filter(AiAssistant.id == calendar.assistant_id).first()
            if assistant is not None:
                self.record_failure(db, assistant, calendar, exc)
            raise
        self._busy_cache[calendar.id] = (clock.monotonic(), busy)
        return busy

    def forget_busy(self, calendar_id: int) -> None:
        """Drop an agenda's cached busy periods (after a booking, a new agenda id, a reconnection)."""
        self._busy_cache.pop(calendar_id, None)

    async def access_token(self, db: Session, calendar: AiAssistantCalendar) -> str:
        """
        A valid access token, refreshed (and stored) when it expires within two minutes.

        Args:
            db: Active database session.
            calendar: The agenda.

        Returns:
            The access token.

        Raises:
            GoogleCalendarError: When the agenda has no lasting access, or Google refuses to refresh it.
        """
        now_utc = datetime.now(UTC).replace(tzinfo=None)
        access_token = self._decrypt(calendar.access_token_encrypted)
        if access_token and calendar.token_expires_at and calendar.token_expires_at > now_utc + timedelta(minutes=2):
            return access_token
        return await self.refresh_access_token(db, calendar)

    async def refresh_access_token(self, db: Session, calendar: AiAssistantCalendar) -> str:
        """
        A new access token from the stored refresh token, saved at once.

        Args:
            db: Active database session.
            calendar: The agenda.

        Returns:
            The fresh access token.

        Raises:
            GoogleCalendarError: When the agenda has no lasting access, or Google refuses to refresh it.
        """
        refresh_token = self._decrypt(calendar.refresh_token_encrypted)
        if not refresh_token:
            raise GoogleCalendarError("Agenda sans accès durable", needs_reconnect=True)
        tokens = await google_calendar_client.refresh(refresh_token)
        calendar.access_token_encrypted = encryption_service.encrypt(tokens.access_token)
        if tokens.refresh_token and tokens.refresh_token != refresh_token:
            calendar.refresh_token_encrypted = encryption_service.encrypt(tokens.refresh_token)
        calendar.token_expires_at = tokens.expires_at
        # Saved at once, in its own short transaction: no write stays open while Google answers next.
        db.commit()
        return tokens.access_token

    async def with_fresh_token(
        self, db: Session, calendar: AiAssistantCalendar, operation: Callable[[str], Awaitable[T]]
    ) -> T:
        """
        Run a Calendar call with a valid token; a 401 (a token Google dropped early) is refreshed once and replayed.

        Args:
            db: Active database session.
            calendar: The agenda.
            operation: The call, given the access token.

        Returns:
            What the call returns.

        Raises:
            GoogleCalendarError: When the call fails again, or the refresh is refused (then a reconnection is due).
        """
        access_token = await self.access_token(db, calendar)
        try:
            return await operation(access_token)
        except GoogleCalendarError as exc:
            if exc.status_code != 401:
                raise
        access_token = await self.refresh_access_token(db, calendar)
        return await operation(access_token)

    def record_failure(
        self, db: Session, assistant: AiAssistant, calendar: AiAssistantCalendar, exc: GoogleCalendarError
    ) -> None:
        """
        Keep what went wrong, for the client space; a lost access puts the agenda in error.

        Args:
            db: Active database session (rolled back first).
            assistant: The assistant.
            calendar: The agenda that failed.
            exc: What Google answered.
        """
        logger.warning("Agenda of assistant %s failed: %s", assistant.id, exc)
        db.rollback()
        row = db.query(AiAssistantCalendar).filter(AiAssistantCalendar.id == calendar.id).first()
        if row is None:
            return
        moment = OpeningHoursCalendar.business_now()
        message = f"{moment:%d/%m à %H:%M} : {self._failure_message(exc)}"[:255]
        if not exc.needs_reconnect:
            row.last_error = message
            db.commit()
            return
        if row.status == AssistantCalendarStatus.ERROR.value:
            return
        row.status = AssistantCalendarStatus.ERROR.value
        row.last_error = message
        db.commit()
        self.forget_busy(calendar.id)
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_calendar_lost",
            status=STATUS_WARNING,
            title=f"{assistant.business_name} · Google Agenda n'est plus accessible",
            detail=(
                f"{exc} : les rendez-vous repassent en demandes de créneaux. Le client doit reconnecter son agenda "
                "depuis son espace."
            ),
            user_id=assistant.user_id,
            entity_type="prospect",
            entity_id=assistant.prospect_id,
        )

    @staticmethod
    def _failure_message(exc: GoogleCalendarError) -> str:
        """What the client reads of a failed agenda call."""
        if exc.needs_reconnect:
            return "l'accès à l'agenda a été perdu, reconnectez-le"
        if exc.status_code == 403:
            return "Google refuse d'écrire dans cet agenda (lecture seule ?), choisissez un agenda modifiable"
        if exc.status_code == 404:
            return "agenda introuvable, vérifiez son identifiant"
        if exc.status_code is None:
            return "Google Agenda n'a pas répondu, les rendez-vous sont passés en demandes à confirmer"
        return f"Google Agenda a refusé l'appel ({exc.status_code})"

    @staticmethod
    def _decrypt(value: str | None) -> str | None:
        """A stored secret in clear, None when absent or unreadable (a rotated key)."""
        if not value:
            return None
        try:
            return encryption_service.decrypt(value) or None
        except ValueError:
            logger.warning("An agenda token could not be decrypted")
            return None


ai_assistant_calendar_access = AiAssistantCalendarAccess()
