"""
A sold assistant's Google agenda: its connection from the client space, and the appointment offer of its widget.

The client connects their agenda from the client space. The widget then offers the first free slot of each of the
next half-days, three at a time (``calendar_slot_grid``), and the visitor's pick is booked (``calendar_booking``).
Without a usable agenda the widget falls back on the half-day wishes of ``appointment_slots.py``.
"""

from __future__ import annotations

import hmac
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from enums.ai_assistant_status import AiAssistantStatus
from enums.assistant_booking_mode import AssistantBookingMode
from enums.assistant_calendar_status import AssistantCalendarConnection, AssistantCalendarStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_calendar import AiAssistantCalendar
from services.activity_log_service import CATEGORY_ASSISTANT, STATUS_SUCCESS, activity_log_service
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots, AppointmentDay
from services.ai_assistant.calendar_access import ai_assistant_calendar_access
from services.ai_assistant.calendar_settings import (
    APPOINTMENT_TYPE_MAX_CHARS,
    DURATION_CHOICES,
    MAX_APPOINTMENT_TYPES,
    MIN_NOTICE_CHOICES,
    CalendarSettings,
)
from services.ai_assistant.calendar_slot_grid import AiAssistantCalendarSlotGrid, SlotPage
from services.ai_assistant.google_calendar_client import (
    GOOGLE_CALENDAR_EVENTS_SCOPE,
    GOOGLE_CALENDAR_FREEBUSY_SCOPE,
    BusyPeriod,
    GoogleCalendarError,
    google_calendar_client,
)
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.signed_token import SignedToken
from services.encryption_service import encryption_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppointmentOffer:
    """What the widget's appointment panel shows: the agenda's free slots, or half-days to wish."""

    mode: AssistantBookingMode
    slots: SlotPage | None
    settings: CalendarSettings | None
    days: list[AppointmentDay]


class AiAssistantCalendarState:
    """The OAuth ``state`` of an agenda connection: the assistant, an expiry and an HMAC of both."""

    TTL_MINUTES: ClassVar[int] = 15
    _PURPOSE: ClassVar[str] = "assistant-calendar-oauth"
    _PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"([1-9][0-9]{0,11})\.([0-9]{1,12})\.([A-Za-z0-9_-]{22})", re.ASCII
    )

    @classmethod
    def sign(cls, assistant_id: int, *, now: datetime | None = None) -> str:
        """
        A state for one consent, valid ``TTL_MINUTES`` minutes.

        Args:
            assistant_id: The assistant whose agenda is being connected.
            now: Current time, naive UTC (tests); defaults to now.

        Returns:
            ``<id>.<expiry epoch>.<signature>``.
        """
        moment = now or datetime.now(UTC).replace(tzinfo=None)
        expiry = str(int((moment + timedelta(minutes=cls.TTL_MINUTES)).replace(tzinfo=UTC).timestamp()))
        return f"{assistant_id}.{expiry}.{cls._signature(assistant_id, expiry)}"

    @classmethod
    def read(cls, state: str, *, now: datetime | None = None) -> int | None:
        """
        The assistant of a state that is authentic and still valid.

        Args:
            state: The ``state`` Google sent back.
            now: Current time, naive UTC (tests); defaults to now.

        Returns:
            The assistant id, or None when the state is forged, malformed or expired.
        """
        match = cls._PATTERN.fullmatch(state or "")
        if match is None:
            return None
        assistant_id, expiry, signature = int(match.group(1)), match.group(2), match.group(3)
        if not hmac.compare_digest(signature, cls._signature(assistant_id, expiry)):
            return None
        moment = now or datetime.now(UTC).replace(tzinfo=None)
        if int(expiry) <= int(moment.replace(tzinfo=UTC).timestamp()):
            return None
        return assistant_id

    @classmethod
    def _signature(cls, assistant_id: int, expiry: str) -> str:
        """Truncated HMAC-SHA256 (128 bits) of the assistant and expiry, base64url without padding."""
        return SignedToken.short(cls._PURPOSE, assistant_id, expiry, length=16)


class AiAssistantCalendarService:
    """Connects a sold assistant's Google agenda and offers its free slots to the widget."""

    @staticmethod
    def authorization_url(assistant: AiAssistant) -> str:
        """
        The Google consent page that connects an assistant's agenda.

        Args:
            assistant: The sold assistant.

        Returns:
            The consent URL, with a signed state valid 15 minutes.

        Raises:
            ValueError: When the Google OAuth client is not configured on the server.
        """
        if not google_calendar_client.is_configured:
            raise ValueError("La connexion Google n'est pas configurée sur le serveur")
        return google_calendar_client.authorization_url(AiAssistantCalendarState.sign(assistant.id))

    async def connect(self, db: Session, *, code: str, state: str) -> tuple[AiAssistant, AiAssistantCalendar]:
        """
        Finish a consent: store the account's tokens (encrypted) on the assistant's agenda.

        Args:
            db: Active database session.
            code: The consent code.
            state: The state signed by :meth:`authorization_url`.

        Returns:
            The assistant and its connected agenda.

        Raises:
            ValueError: When the state is invalid, the assistant is not sold, or the agenda access was not granted.
            GoogleCalendarError: When Google refuses the code.
        """
        assistant_id = AiAssistantCalendarState.read(state)
        if assistant_id is None:
            raise ValueError("Lien de connexion expiré : recommencez depuis votre espace")
        assistant = (
            db.query(AiAssistant)
            .filter(
                AiAssistant.id == assistant_id,
                AiAssistant.deleted_at.is_(None),
                AiAssistant.status == AiAssistantStatus.DELIVERED.value,
            )
            .first()
        )
        if assistant is None:
            raise ValueError("Cet assistant ne peut pas recevoir d'agenda")
        tokens = await google_calendar_client.exchange_code(code)
        # Google lets the client untick a permission: without both, nothing is stored.
        if not {GOOGLE_CALENDAR_EVENTS_SCOPE, GOOGLE_CALENDAR_FREEBUSY_SCOPE} <= tokens.scopes:
            raise ValueError("Cochez les deux accès à l'agenda dans la fenêtre de Google")
        if not tokens.refresh_token:
            raise ValueError("Google n'a pas donné d'accès durable : recommencez")
        account_email = await google_calendar_client.account_email(tokens.access_token)

        # A reconnection replaces the tokens; the old ones are not revoked (revoking one token of an account
        # revokes all of its grant, the new tokens included).
        calendar = ai_assistant_calendar_access.calendar_of(db, assistant)
        if calendar is None:
            calendar = AiAssistantCalendar(user_id=assistant.user_id, assistant_id=assistant.id)
            db.add(calendar)
        elif calendar.account_email != account_email:
            # Another Google account: the agenda chosen in the previous one is not in it.
            calendar.calendar_id = "primary"
        calendar.provider = "google"
        calendar.account_email = account_email
        calendar.access_token_encrypted = encryption_service.encrypt(tokens.access_token)
        calendar.refresh_token_encrypted = encryption_service.encrypt(tokens.refresh_token)
        calendar.token_expires_at = tokens.expires_at
        calendar.status = AssistantCalendarStatus.CONNECTED.value
        calendar.last_error = None
        calendar.connected_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
        db.refresh(calendar)
        ai_assistant_calendar_access.forget_busy(calendar.id)
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_calendar_connected",
            status=STATUS_SUCCESS,
            title=f"{assistant.business_name} · Google Agenda connecté depuis l'espace client",
            detail=account_email or "adresse du compte inconnue",
            user_id=assistant.user_id,
            entity_type="prospect",
            entity_id=assistant.prospect_id,
        )
        return assistant, calendar

    def disconnect(self, db: Session, assistant: AiAssistant) -> None:
        """
        Forget an assistant's agenda: its tokens are deleted here.

        The access is not revoked at Google: a revocation covers the whole grant of the Google account, which may
        serve elsewhere (another assistant, the operator's own Google connections). The client removes it from
        their Google account if they wish.

        Args:
            db: Active database session.
            assistant: The assistant.
        """
        calendar = ai_assistant_calendar_access.calendar_of(db, assistant)
        if calendar is None:
            return
        ai_assistant_calendar_access.forget_busy(calendar.id)
        db.delete(calendar)
        db.commit()

    async def update_settings(
        self, db: Session, calendar: AiAssistantCalendar, changes: dict[str, Any]
    ) -> AiAssistantCalendar:
        """
        Change an agenda's booking settings.

        Args:
            db: Active database session.
            calendar: The agenda.
            changes: ``calendar_id``, ``duration_minutes``, ``min_notice_hours``, ``appointment_types``
                (absent keys are kept; checked by the request schema).

        Returns:
            The updated agenda.

        Raises:
            ValueError: When a value is outside the offered choices, or Google cannot read the agenda id.
        """
        # The agenda id is checked first: nothing is changed when Google cannot read it.
        wanted = (changes.get("calendar_id") or "").strip() or "primary" if "calendar_id" in changes else None
        if wanted is not None and wanted != calendar.calendar_id:
            await self._check_calendar_id(db, calendar, wanted)
        if "duration_minutes" in changes:
            if changes["duration_minutes"] not in DURATION_CHOICES:
                raise ValueError("Durée non proposée")
            calendar.duration_minutes = changes["duration_minutes"]
        if "min_notice_hours" in changes:
            if changes["min_notice_hours"] not in MIN_NOTICE_CHOICES:
                raise ValueError("Délai non proposé")
            calendar.min_notice_hours = changes["min_notice_hours"]
        if "appointment_types" in changes:
            labels: list[str] = []
            for label in changes["appointment_types"] or []:
                cleaned = " ".join(str(label).split())[:APPOINTMENT_TYPE_MAX_CHARS]
                if cleaned and cleaned.casefold() not in {existing.casefold() for existing in labels}:
                    labels.append(cleaned)
            calendar.appointment_types_json = labels[:MAX_APPOINTMENT_TYPES] or None
        if wanted is not None and wanted != calendar.calendar_id:
            calendar.calendar_id = wanted
            calendar.last_error = None
            ai_assistant_calendar_access.forget_busy(calendar.id)
        db.commit()
        db.refresh(calendar)
        return calendar

    async def _check_calendar_id(self, db: Session, calendar: AiAssistantCalendar, calendar_id: str) -> None:
        """Refuse an agenda id Google cannot read with the connected account."""
        start = datetime.now(UTC).replace(tzinfo=None)
        try:
            access_token = await ai_assistant_calendar_access.access_token(db, calendar)
            await google_calendar_client.busy_periods(
                access_token, calendar_id, start=start, end=start + timedelta(hours=1)
            )
        except GoogleCalendarError as exc:
            if exc.needs_reconnect:
                raise ValueError("L'accès à l'agenda a été perdu : reconnectez-le d'abord") from exc
            raise ValueError("Agenda introuvable avec ce compte : vérifiez son identifiant") from exc

    def connection(
        self, db: Session, assistant: AiAssistant
    ) -> tuple[AssistantCalendarConnection, AiAssistantCalendar | None]:
        """
        Where the assistant's agenda stands, as the client space shows it.

        Args:
            db: Active database session.
            assistant: The sold assistant.

        Returns:
            The connection state and the agenda row, if any.
        """
        calendar = ai_assistant_calendar_access.calendar_of(db, assistant)
        if not google_calendar_client.is_configured:
            return AssistantCalendarConnection.UNAVAILABLE, calendar
        if calendar is None:
            return AssistantCalendarConnection.DISCONNECTED, None
        if calendar.status == AssistantCalendarStatus.ERROR.value:
            return AssistantCalendarConnection.ERROR, calendar
        return AssistantCalendarConnection.CONNECTED, calendar

    async def offer(self, db: Session, assistant: AiAssistant, *, after: datetime | None = None) -> AppointmentOffer:
        """
        The appointment panel of a widget: free slots of a usable agenda, else the open half-days.

        Args:
            db: Active database session.
            assistant: The assistant.
            after: A free slot already shown (the next page starts at the half-day after it).

        Returns:
            The offer; an agenda out of reach falls back on the half-days.
        """
        calendar = ai_assistant_calendar_access.usable_calendar(db, assistant)
        if calendar is not None:
            try:
                page = await self.free_slots(db, assistant, calendar, after=after)
            except GoogleCalendarError:
                logger.warning("Free slots of assistant %s unavailable, half-days offered", assistant.id)
            else:
                return AppointmentOffer(
                    mode=AssistantBookingMode.CALENDAR, slots=page, settings=CalendarSettings.of(calendar), days=[]
                )
        return AppointmentOffer(
            mode=AssistantBookingMode.REQUEST,
            slots=None,
            settings=None,
            days=AiAssistantAppointmentSlots.offer_for(assistant),
        )

    async def free_slots(
        self,
        db: Session,
        assistant: AiAssistant,
        calendar: AiAssistantCalendar,
        *,
        after: datetime | None = None,
        now: datetime | None = None,
    ) -> SlotPage:
        """
        The next free slots, one per half-day, three at a time.

        Args:
            db: Active database session.
            assistant: The sold assistant (its knowledge holds the opening hours).
            calendar: Its connected agenda.
            after: A slot already shown: the page starts at the half-day after it.
            now: Current business time, aware (tests); defaults to now.

        Returns:
            The slots and whether more follow.

        Raises:
            GoogleCalendarError: When the agenda cannot be read.
        """
        local_now = OpeningHoursCalendar.localize(now or OpeningHoursCalendar.business_now())
        busy = await ai_assistant_calendar_access.busy_periods(db, calendar, local_now)
        # Appointments booked here count as busy even before the agenda shows them.
        booked = (
            db.query(AiAssistantAppointment.starts_at, AiAssistantAppointment.ends_at)
            .filter(
                AiAssistantAppointment.assistant_id == assistant.id,
                AiAssistantAppointment.google_event_id.isnot(None),
                AiAssistantAppointment.ends_at > OpeningHoursCalendar.to_utc(local_now),
            )
            .all()
        )
        return AiAssistantCalendarSlotGrid.compute_slots(
            opening_hours=AiAssistantAppointmentSlots.opening_hours_of(assistant),
            busy=[*busy, *(BusyPeriod(start=start, end=end) for start, end in booked)],
            settings=CalendarSettings.of(calendar),
            now=local_now,
            after=after,
            count=AiAssistantCalendarSlotGrid.SLOTS_PER_PAGE,
        )


ai_assistant_calendar_service = AiAssistantCalendarService()
