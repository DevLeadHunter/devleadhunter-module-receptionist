"""
Booking in a sold assistant's Google agenda: the connection, the free slots of the widget, the booking.

The client connects their agenda from the client space. The widget then offers the first free slot of each
of the next half-days (three at a time) inside the business hours, after a minimum notice; the visitor picks
one and the appointment is created in the agenda. Without a usable agenda the widget falls back on the
half-day wishes of ``appointment_slots.py``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import re
import time as clock
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from core.config import settings
from enums.ai_assistant_request import AiAssistantDayPeriod, AiAssistantRequestType
from enums.ai_assistant_status import AiAssistantStatus
from enums.assistant_booking_mode import AssistantBookingMode
from enums.assistant_calendar_status import AssistantCalendarConnection, AssistantCalendarStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_calendar import AiAssistantCalendar
from models.ai_assistant_request import AiAssistantRequest
from services.activity_log_service import CATEGORY_ASSISTANT, STATUS_SUCCESS, STATUS_WARNING, activity_log_service
from services.ai_assistant.appointment_slots import (
    AiAssistantAppointmentSlots,
    AppointmentDay,
    AppointmentRefused,
    AppointmentSlot,
)
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.google_calendar_client import (
    GOOGLE_CALENDAR_EVENTS_SCOPE,
    GOOGLE_CALENDAR_FREEBUSY_SCOPE,
    BusyPeriod,
    CalendarEventDraft,
    GoogleCalendarError,
    google_calendar_client,
)
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.encryption_service import encryption_service
from services.sms.phone_normalizer import to_e164_mobile

logger = logging.getLogger(__name__)

DEFAULT_DURATION_MINUTES = 60
DEFAULT_MIN_NOTICE_HOURS = 24
DURATION_CHOICES: tuple[int, ...] = (15, 30, 45, 60, 90, 120, 180)
MIN_NOTICE_CHOICES: tuple[int, ...] = (0, 2, 4, 12, 24, 48, 72)
MAX_APPOINTMENT_TYPES = 6
APPOINTMENT_TYPE_MAX_CHARS = 40
# Visitors are texted only on a mobile of the countries the assistants serve (like the alert mobile).
VISITOR_SMS_PREFIXES: tuple[str, ...] = ("+33", "+32", "+352", "+41", "+49")


_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class SlotTakenError(Exception):
    """The slot is no longer free: booked in between, or busy in the agenda."""


@dataclass(frozen=True)
class AppointmentOffer:
    """What the widget's appointment panel shows: the agenda's free slots, or half-days to wish."""

    mode: AssistantBookingMode
    slots: SlotPage | None
    settings: CalendarSettings | None
    days: list[AppointmentDay]


@dataclass(frozen=True)
class BookingOutcome:
    """A visitor's pick: the appointment created in the agenda, or None when it was kept as a wished half-day."""

    appointment: AiAssistantAppointment | None


@dataclass(frozen=True)
class CalendarSettings:
    """The booking settings of an agenda, defaults applied."""

    calendar_id: str
    duration_minutes: int
    min_notice_hours: int
    appointment_types: tuple[str, ...]

    @classmethod
    def defaults(cls) -> CalendarSettings:
        """The settings of an agenda nobody changed."""
        return cls(
            calendar_id="primary",
            duration_minutes=DEFAULT_DURATION_MINUTES,
            min_notice_hours=DEFAULT_MIN_NOTICE_HOURS,
            appointment_types=(),
        )

    @classmethod
    def of(cls, calendar: AiAssistantCalendar) -> CalendarSettings:
        """
        Read an agenda's settings.

        Args:
            calendar: The connected agenda.

        Returns:
            Its settings; ``NULL`` columns read as the defaults.
        """
        types = calendar.appointment_types_json if isinstance(calendar.appointment_types_json, list) else []
        return cls(
            calendar_id=calendar.calendar_id or "primary",
            duration_minutes=calendar.duration_minutes or DEFAULT_DURATION_MINUTES,
            min_notice_hours=(
                DEFAULT_MIN_NOTICE_HOURS if calendar.min_notice_hours is None else calendar.min_notice_hours
            ),
            appointment_types=tuple(str(label) for label in types if str(label).strip()),
        )


@dataclass(frozen=True)
class FreeSlot:
    """A free slot, aware in the business time zone."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class SlotPage:
    """The slots offered at once, and whether later half-days have more."""

    slots: list[FreeSlot]
    has_more: bool


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
        message = f"{cls._PURPOSE}:{assistant_id}:{expiry}".encode()
        digest = hmac.new(settings.secret_key.encode(), message, hashlib.sha256).digest()[:16]
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")


class AiAssistantCalendarService:
    """Connects a sold assistant's Google agenda, offers its free slots and books them."""

    SLOTS_PER_PAGE: ClassVar[int] = 3
    LOOK_AHEAD_DAYS: ClassVar[int] = 21
    # Candidate starts, business time: the day's first and last possible start.
    FIRST_START: ClassVar[time] = time(6, 0)
    LAST_START: ClassVar[time] = time(21, 30)
    PROBE_MINUTES: ClassVar[int] = 15
    # A slot starting before 13:00 belongs to the morning.
    AFTERNOON_FROM: ClassVar[time] = time(13, 0)
    # Hours of a day whose opening hours are unknown (Monday to Friday only).
    FALLBACK_RANGES: ClassVar[tuple[tuple[time, time], ...]] = ((time(9, 0), time(12, 0)), (time(14, 0), time(18, 0)))
    BUSY_CACHE_SECONDS: ClassVar[float] = 60.0
    REMINDER_HOURS_BEFORE: ClassVar[int] = 24
    # The reminder never leaves before 9:00 nor from 20:00 (business time).
    REMINDER_EARLIEST: ClassVar[time] = time(9, 0)
    REMINDER_LATEST: ClassVar[time] = time(19, 0)
    REMINDER_MIN_GAP: ClassVar[timedelta] = timedelta(hours=2)

    MAX_BOOKINGS_PER_DAY: ClassVar[int] = 20

    def __init__(self) -> None:
        # Busy periods per agenda, for a minute: the widget's slot page is not a Google call per visitor click.
        self._busy_cache: dict[int, tuple[float, datetime, list[BusyPeriod]]] = {}
        # One booking at a time per agenda (the API runs a single worker).
        self._locks: dict[int, asyncio.Lock] = {}

    # --- Connection -------------------------------------------------------------------------------

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
        calendar = self.calendar_of(db, assistant)
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
        self._busy_cache.pop(calendar.id, None)
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
        calendar = self.calendar_of(db, assistant)
        if calendar is None:
            return
        self._busy_cache.pop(calendar.id, None)
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
            self._busy_cache.pop(calendar.id, None)
        db.commit()
        db.refresh(calendar)
        return calendar

    # --- Free slots -------------------------------------------------------------------------------

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
        calendar = self.usable_calendar(db, assistant)
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
        local_now = self._local(now or OpeningHoursCalendar.business_now())
        busy = await self._busy(db, calendar, local_now)
        # Appointments booked here count as busy even before the agenda shows them.
        booked = (
            db.query(AiAssistantAppointment.starts_at, AiAssistantAppointment.ends_at)
            .filter(
                AiAssistantAppointment.assistant_id == assistant.id,
                AiAssistantAppointment.google_event_id.isnot(None),
                AiAssistantAppointment.ends_at > local_now.astimezone(UTC).replace(tzinfo=None),
            )
            .all()
        )
        return self.compute_slots(
            opening_hours=self._opening_hours(assistant),
            busy=[*busy, *(BusyPeriod(start=start, end=end) for start, end in booked)],
            settings=CalendarSettings.of(calendar),
            now=local_now,
            after=after,
            count=self.SLOTS_PER_PAGE,
        )

    @classmethod
    def compute_slots(
        cls,
        *,
        opening_hours: list[dict[str, str]] | None,
        busy: list[BusyPeriod],
        settings: CalendarSettings,
        now: datetime,
        after: datetime | None,
        count: int,
    ) -> SlotPage:
        """
        The first free slot of each half-day, from the minimum notice on, within the business hours.

        Args:
            opening_hours: The business's cleaned opening-hour rows, when known.
            busy: The agenda's busy periods, naive UTC.
            settings: The booking settings.
            now: Current business time, aware.
            after: A slot already shown (the page starts at the half-day after it).
            count: How many slots to return.

        Returns:
            At most ``count`` slots, in order, and whether more follow.
        """
        tz = OpeningHoursCalendar.business_timezone()
        local_now = now.astimezone(tz)
        earliest = local_now + timedelta(hours=settings.min_notice_hours)
        duration = timedelta(minutes=settings.duration_minutes)
        grid = cls._grid_minutes(settings.duration_minutes)
        skip_until = cls._half_day(cls._local(after)) if after is not None else None
        open_cache: dict[datetime, bool] = {}
        slots: list[FreeSlot] = []
        seen: set[tuple[date, int]] = set()
        for offset in range(cls.LOOK_AHEAD_DAYS + 1):
            day = local_now.date() + timedelta(days=offset)
            for start_naive in cls._candidate_starts(day, grid):
                start = start_naive.replace(tzinfo=tz)
                key = cls._half_day(start)
                if key in seen or (skip_until is not None and key <= skip_until) or start < earliest:
                    continue
                end = start + duration
                if not cls._open_throughout(opening_hours, start_naive, duration, open_cache):
                    continue
                if cls._overlaps(busy, start, end):
                    continue
                seen.add(key)
                slots.append(FreeSlot(start=start, end=end))
                if len(slots) > count:
                    return SlotPage(slots=slots[:count], has_more=True)
        return SlotPage(slots=slots, has_more=False)

    # --- Booking ----------------------------------------------------------------------------------

    async def book_request(
        self,
        db: Session,
        assistant: AiAssistant,
        request: AiAssistantRequest,
        *,
        start: datetime,
        type_label: str | None,
        now: datetime | None = None,
    ) -> BookingOutcome:
        """
        Book the slot a visitor picked for their request, or keep it as a wished half-day.

        Without a usable agenda (disconnected meanwhile, Google out of reach), the request keeps the half-day of
        the picked slot and the business confirms it, as in the half-day fallback.

        Args:
            db: Active database session (committed).
            assistant: The assistant.
            request: The visitor's request, already captured.
            start: The picked start, aware.
            type_label: The picked kind of appointment.
            now: Current business time, aware (tests); defaults to now.

        Returns:
            The outcome; the request is an appointment request either way (unless urgent).

        Raises:
            AppointmentRefused: When the slot or the kind is not one the widget offers.
            SlotTakenError: When the slot is no longer free.
        """
        local_now = self._local(now or OpeningHoursCalendar.business_now())
        calendar = self.usable_calendar(db, assistant)
        if calendar is not None and self._bookings_today(db, assistant, local_now) >= self.MAX_BOOKINGS_PER_DAY:
            # A day's bookings are capped: past the cap (a script, a flood), picks become wishes and no message
            # leaves for a visitor.
            logger.warning("Assistant %s reached %s bookings in 24 h", assistant.id, self.MAX_BOOKINGS_PER_DAY)
            calendar = None
        if calendar is not None:
            phone, email = self.visitor_channels(db, assistant, request.contact)
            try:
                appointment = await self.book(
                    db,
                    assistant,
                    calendar,
                    request,
                    start=start,
                    type_label=type_label,
                    visitor_phone_e164=phone,
                    visitor_email=email,
                    now=local_now,
                )
            except GoogleCalendarError:
                logger.warning("Booking of request %s falls back on a wished half-day", request.id)
            else:
                self._mark_appointment(request)
                db.commit()
                return BookingOutcome(appointment=appointment)

        local_start = self._local(start)
        if not local_now <= local_start <= local_now + timedelta(days=self.LOOK_AHEAD_DAYS + 1):
            raise AppointmentRefused("Ce créneau n'est plus proposé")
        period = (
            AiAssistantDayPeriod.MORNING
            if local_start.time().replace(tzinfo=None) < self.AFTERNOON_FROM
            else AiAssistantDayPeriod.AFTERNOON
        )
        request.appointment_slots_json = AiAssistantAppointmentSlots.to_json(
            [AppointmentSlot(day=local_start.date(), period=period)]
        )
        self._mark_appointment(request)
        db.commit()
        return BookingOutcome(appointment=None)

    @staticmethod
    def visitor_channels(db: Session, assistant: AiAssistant, contact: str) -> tuple[str | None, str | None]:
        """
        Where a visitor can be told: their mobile (read like the business's own country) and their address.

        Args:
            db: Active database session.
            assistant: The assistant.
            contact: What the visitor typed.

        Returns:
            ``(mobile in E.164 or None, email or None)``.
        """
        cleaned = " ".join((contact or "").split())
        email = _EMAIL_PATTERN.fullmatch(cleaned)
        if email is not None:
            return None, cleaned.lower()[:255]
        mobile = to_e164_mobile(cleaned, country=ai_assistant_service.business_country(db, assistant))
        return (mobile if mobile and mobile.startswith(VISITOR_SMS_PREFIXES) else None), None

    async def book(
        self,
        db: Session,
        assistant: AiAssistant,
        calendar: AiAssistantCalendar,
        request: AiAssistantRequest,
        *,
        start: datetime,
        type_label: str | None,
        visitor_phone_e164: str | None,
        visitor_email: str | None,
        now: datetime | None = None,
    ) -> AiAssistantAppointment:
        """
        Book a slot: checked again against the agenda, then created in it.

        Bookings of one agenda run one at a time (an in-process lock; the API runs one worker). No database lock
        nor open write is held while Google answers: the event is created first, with an id derived from the
        request and the slot (a repeated insert finds it), then the appointment is saved in one short transaction.

        Args:
            db: Active database session (committed).
            assistant: The sold assistant.
            calendar: Its connected agenda.
            request: The visitor's request (name, contact, need), already captured.
            start: The chosen start, aware.
            type_label: The chosen kind of appointment (required when the agenda offers kinds).
            visitor_phone_e164: The visitor's mobile, when they left one.
            visitor_email: The visitor's address, when they left one.
            now: Current business time, aware (tests); defaults to now.

        Returns:
            The booked appointment; a request that already has one gets it back (one appointment per request).

        Raises:
            AppointmentRefused: When the slot or the kind is not one the widget offers.
            SlotTakenError: When the slot is no longer free.
            GoogleCalendarError: When the agenda cannot be read or written.
        """
        tz = OpeningHoursCalendar.business_timezone()
        local_now = self._local(now or OpeningHoursCalendar.business_now())
        booking_settings = CalendarSettings.of(calendar)
        local_start = self._local(start)
        duration = timedelta(minutes=booking_settings.duration_minutes)
        chosen_type = self._check_type(booking_settings, type_label)
        self._check_start(assistant, booking_settings, local_start, local_now)
        start_utc = local_start.astimezone(UTC).replace(tzinfo=None)
        end_utc = start_utc + duration

        async with self._lock_for(calendar.id):
            # A fresh transaction: the checks below see the bookings committed a moment ago.
            db.commit()
            already = (
                db.query(AiAssistantAppointment)
                .filter(
                    AiAssistantAppointment.request_id == request.id,
                    AiAssistantAppointment.google_event_id.isnot(None),
                )
                .first()
            )
            if already is not None:
                return already
            taken = (
                db.query(AiAssistantAppointment.id)
                .filter(
                    AiAssistantAppointment.assistant_id == assistant.id,
                    AiAssistantAppointment.google_event_id.isnot(None),
                    AiAssistantAppointment.starts_at < end_utc,
                    AiAssistantAppointment.ends_at > start_utc,
                )
                .first()
            )
            try:
                access_token = await self._access_token(db, calendar)
                busy = await google_calendar_client.busy_periods(
                    access_token, booking_settings.calendar_id, start=start_utc, end=end_utc
                )
            except GoogleCalendarError as exc:
                self._record_failure(db, assistant, calendar, exc)
                raise
            if taken is not None or self._overlaps(busy, local_start, local_start + duration):
                self._busy_cache.pop(calendar.id, None)
                raise SlotTakenError("Ce créneau vient d'être pris")

            draft = CalendarEventDraft(
                event_id=self._event_id(request.id, start_utc),
                summary=self._event_summary(request, chosen_type),
                description=self._event_description(assistant, request),
                start=local_start,
                end=local_start + duration,
                time_zone=getattr(tz, "key", "UTC"),
                request_id=request.id,
            )
            try:
                event_id = await self._insert_event(access_token, booking_settings.calendar_id, draft)
            except GoogleCalendarError as exc:
                self._record_failure(db, assistant, calendar, exc)
                raise
            appointment = AiAssistantAppointment(
                user_id=assistant.user_id,
                assistant_id=assistant.id,
                request_id=request.id,
                starts_at=start_utc,
                ends_at=end_utc,
                type_label=chosen_type,
                google_event_id=event_id,
                visitor_phone_e164=visitor_phone_e164,
                visitor_email=visitor_email,
                language=request.language,
                is_test=bool(request.is_test),
                reminder_due_at=self.reminder_due_at(
                    start_utc, booked_at=local_now.astimezone(UTC).replace(tzinfo=None)
                ),
            )
            db.add(appointment)
            if calendar.last_error:
                calendar.last_error = None
            db.commit()
            db.refresh(appointment)
        self._busy_cache.pop(calendar.id, None)
        return appointment

    @classmethod
    def reminder_due_at(cls, start_utc: datetime, *, booked_at: datetime) -> datetime | None:
        """
        When the visitor's J-1 reminder leaves: 24 hours before, kept between 9:00 and 19:00 (business time).

        Args:
            start_utc: The appointment's start, naive UTC.
            booked_at: When it was booked, naive UTC.

        Returns:
            The due moment, naive UTC, or None when it would come less than 2 hours after the booking.
        """
        tz = OpeningHoursCalendar.business_timezone()
        due = OpeningHoursCalendar.to_business_time(start_utc) - timedelta(hours=cls.REMINDER_HOURS_BEFORE)
        if due.time() < cls.REMINDER_EARLIEST:
            due = datetime.combine(due.date(), cls.REMINDER_EARLIEST, tzinfo=tz)
        elif due.time() > cls.REMINDER_LATEST:
            due = datetime.combine(due.date(), cls.REMINDER_LATEST, tzinfo=tz)
        due_utc = due.astimezone(UTC).replace(tzinfo=None)
        return due_utc if due_utc > booked_at + cls.REMINDER_MIN_GAP else None

    @staticmethod
    def start_label(appointment: AiAssistantAppointment) -> str:
        """An appointment's start for the business (« mar. 29/09 à 14:30 »)."""
        start = OpeningHoursCalendar.to_business_time(appointment.starts_at)
        weekday = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")[start.weekday()]
        return f"{weekday} {start:%d/%m} à {start:%H:%M}"

    @classmethod
    def booked_label(cls, appointment: AiAssistantAppointment) -> str:
        """An appointment for the business (« mar. 29/09 à 14:30 (Révision) »)."""
        label = cls.start_label(appointment)
        return f"{label} ({appointment.type_label})" if appointment.type_label else label

    def booked_labels(self, db: Session, request_ids: list[int]) -> dict[int, str]:
        """
        The booked appointment of each request that has one.

        Args:
            db: Active database session.
            request_ids: The requests.

        Returns:
            ``{request id: label}`` (see :meth:`booked_label`).
        """
        if not request_ids:
            return {}
        rows = (
            db.query(AiAssistantAppointment)
            .filter(
                AiAssistantAppointment.request_id.in_(request_ids),
                AiAssistantAppointment.google_event_id.isnot(None),
            )
            .order_by(AiAssistantAppointment.id.asc())
            .all()
        )
        return {row.request_id: self.booked_label(row) for row in rows}

    @staticmethod
    def upcoming(
        db: Session, assistant: AiAssistant, *, limit: int = 10
    ) -> list[tuple[AiAssistantAppointment, AiAssistantRequest]]:
        """
        The assistant's next booked appointments and their requests (tests excluded).

        Args:
            db: Active database session.
            assistant: The assistant.
            limit: How many at most.

        Returns:
            The appointments not over yet, soonest first, each with its request (the visitor's name and contact).
        """
        now_utc = datetime.now(UTC).replace(tzinfo=None)
        rows = (
            db.query(AiAssistantAppointment, AiAssistantRequest)
            .join(AiAssistantRequest, AiAssistantRequest.id == AiAssistantAppointment.request_id)
            .filter(
                AiAssistantAppointment.assistant_id == assistant.id,
                AiAssistantAppointment.google_event_id.isnot(None),
                AiAssistantAppointment.is_test.is_(False),
                AiAssistantAppointment.ends_at > now_utc,
            )
            .order_by(AiAssistantAppointment.starts_at.asc())
            .limit(limit)
            .all()
        )
        return [(appointment, request) for appointment, request in rows]

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
        calendar = self.calendar_of(db, assistant)
        if not google_calendar_client.is_configured:
            return AssistantCalendarConnection.UNAVAILABLE, calendar
        if calendar is None:
            return AssistantCalendarConnection.DISCONNECTED, None
        if calendar.status == AssistantCalendarStatus.ERROR.value:
            return AssistantCalendarConnection.ERROR, calendar
        return AssistantCalendarConnection.CONNECTED, calendar

    # --- Internals --------------------------------------------------------------------------------

    def _lock_for(self, calendar_id: int) -> asyncio.Lock:
        """The lock that makes one agenda's bookings run one at a time."""
        return self._locks.setdefault(calendar_id, asyncio.Lock())

    @staticmethod
    def _event_id(request_id: int, start_utc: datetime) -> str:
        """Our id of the Google event of a request's slot: the same request and slot always give the same id."""
        message = f"assistant-event:{request_id}:{start_utc.isoformat()}".encode()
        digest = hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()[:26]
        # Google accepts the letters a to v and digits: hexadecimal fits.
        return f"dlh{digest}"

    @staticmethod
    async def _insert_event(access_token: str, calendar_id: str, draft: CalendarEventDraft) -> str:
        """Create the event, once more after a network failure (the same id makes the retry harmless)."""
        try:
            return await google_calendar_client.insert_event(access_token, calendar_id, draft)
        except GoogleCalendarError as exc:
            if exc.status_code is not None:
                raise
            return await google_calendar_client.insert_event(access_token, calendar_id, draft)

    @staticmethod
    def _bookings_today(db: Session, assistant: AiAssistant, local_now: datetime) -> int:
        """How many appointments the assistant booked over the last 24 hours."""
        since = local_now.astimezone(UTC).replace(tzinfo=None) - timedelta(days=1)
        return (
            db.query(AiAssistantAppointment)
            .filter(AiAssistantAppointment.assistant_id == assistant.id, AiAssistantAppointment.created_at >= since)
            .count()
        )

    async def _check_calendar_id(self, db: Session, calendar: AiAssistantCalendar, calendar_id: str) -> None:
        """Refuse an agenda id Google cannot read with the connected account."""
        start = datetime.now(UTC).replace(tzinfo=None)
        try:
            access_token = await self._access_token(db, calendar)
            await google_calendar_client.busy_periods(
                access_token, calendar_id, start=start, end=start + timedelta(hours=1)
            )
        except GoogleCalendarError as exc:
            if exc.needs_reconnect:
                raise ValueError("L'accès à l'agenda a été perdu : reconnectez-le d'abord") from exc
            raise ValueError("Agenda introuvable avec ce compte : vérifiez son identifiant") from exc

    async def _busy(self, db: Session, calendar: AiAssistantCalendar, local_now: datetime) -> list[BusyPeriod]:
        """The agenda's busy periods over the offer window (cached a minute per agenda)."""
        cached = self._busy_cache.get(calendar.id)
        if cached is not None and clock.monotonic() - cached[0] < self.BUSY_CACHE_SECONDS:
            return cached[2]
        start = local_now.astimezone(UTC).replace(tzinfo=None)
        end = start + timedelta(days=self.LOOK_AHEAD_DAYS + 1)
        try:
            access_token = await self._access_token(db, calendar)
            busy = await google_calendar_client.busy_periods(
                access_token, CalendarSettings.of(calendar).calendar_id, start=start, end=end
            )
        except GoogleCalendarError as exc:
            assistant = db.query(AiAssistant).filter(AiAssistant.id == calendar.assistant_id).first()
            if assistant is not None:
                self._record_failure(db, assistant, calendar, exc)
            raise
        self._busy_cache[calendar.id] = (clock.monotonic(), start, busy)
        return busy

    async def _access_token(self, db: Session, calendar: AiAssistantCalendar) -> str:
        """A valid access token, refreshed (and stored) when it expires within two minutes."""
        now_utc = datetime.now(UTC).replace(tzinfo=None)
        access_token = self._decrypt(calendar.access_token_encrypted)
        if access_token and calendar.token_expires_at and calendar.token_expires_at > now_utc + timedelta(minutes=2):
            return access_token
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

    def _record_failure(
        self, db: Session, assistant: AiAssistant, calendar: AiAssistantCalendar, exc: GoogleCalendarError
    ) -> None:
        """Keep what went wrong (the client space shows it); a lost access puts the agenda in error."""
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
        self._busy_cache.pop(calendar.id, None)
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

    def _check_start(
        self, assistant: AiAssistant, booking_settings: CalendarSettings, local_start: datetime, local_now: datetime
    ) -> None:
        """Refuse a start the widget would never offer (off the grid, too soon, too far, outside the hours)."""
        grid = self._grid_minutes(booking_settings.duration_minutes)
        on_grid = local_start.second == 0 and local_start.microsecond == 0 and local_start.minute % grid == 0
        in_window = (
            local_now + timedelta(hours=booking_settings.min_notice_hours)
            <= local_start
            <= local_now + timedelta(days=self.LOOK_AHEAD_DAYS + 1)
        )
        within_day = self.FIRST_START <= local_start.time().replace(tzinfo=None) <= self.LAST_START
        is_open = self._open_throughout(
            self._opening_hours(assistant),
            local_start.replace(tzinfo=None),
            timedelta(minutes=booking_settings.duration_minutes),
            {},
        )
        if not (on_grid and in_window and within_day and is_open):
            raise AppointmentRefused("Ce créneau n'est plus proposé")

    @staticmethod
    def _mark_appointment(request: AiAssistantRequest) -> None:
        """A picked slot makes the request an appointment request (an urgency stays urgent)."""
        if request.type != AiAssistantRequestType.URGENT.value:
            request.type = AiAssistantRequestType.APPOINTMENT.value

    @staticmethod
    def _check_type(booking_settings: CalendarSettings, type_label: str | None) -> str | None:
        """The chosen kind, required and known when the agenda offers kinds."""
        if not booking_settings.appointment_types:
            return None
        chosen = " ".join((type_label or "").split())
        for offered in booking_settings.appointment_types:
            if offered.casefold() == chosen.casefold():
                return offered
        raise AppointmentRefused("Choisissez le type de rendez-vous")

    @classmethod
    def _candidate_starts(cls, day: date, grid: int) -> list[datetime]:
        """The possible starts of a day, naive business time."""
        moment = datetime.combine(day, cls.FIRST_START)
        last = datetime.combine(day, cls.LAST_START)
        starts: list[datetime] = []
        while moment <= last:
            starts.append(moment)
            moment += timedelta(minutes=grid)
        return starts

    @classmethod
    def _open_throughout(
        cls,
        opening_hours: list[dict[str, str]] | None,
        start: datetime,
        duration: timedelta,
        cache: dict[datetime, bool],
    ) -> bool:
        """Whether the business is open over the whole slot (probed every 15 minutes, naive business time)."""
        probe = start
        while probe < start + duration:
            if probe not in cache:
                cache[probe] = cls._is_open(opening_hours, probe)
            if not cache[probe]:
                return False
            probe += timedelta(minutes=cls.PROBE_MINUTES)
        return True

    @classmethod
    def _is_open(cls, opening_hours: list[dict[str, str]] | None, moment: datetime) -> bool:
        """Open at a moment; a day with unknown hours is open 9:00-12:00 and 14:00-18:00 on weekdays."""
        answer = OpeningHoursCalendar.is_open_at(opening_hours, moment)
        if answer is not None:
            return answer
        if moment.weekday() >= 5:
            return False
        return any(start <= moment.time() < end for start, end in cls.FALLBACK_RANGES)

    @staticmethod
    def _overlaps(busy: list[BusyPeriod], start: datetime, end: datetime) -> bool:
        """Whether an aware slot meets a busy period (naive UTC)."""
        start_utc = start.astimezone(UTC).replace(tzinfo=None)
        end_utc = end.astimezone(UTC).replace(tzinfo=None)
        return any(period.start < end_utc and start_utc < period.end for period in busy)

    @classmethod
    def _half_day(cls, moment: datetime) -> tuple[date, int]:
        """The half-day of a business-time moment (0 morning, 1 afternoon)."""
        return moment.date(), 0 if moment.time().replace(tzinfo=None) < cls.AFTERNOON_FROM else 1

    @staticmethod
    def _grid_minutes(duration_minutes: int) -> int:
        """Starts every 30 minutes, every 15 for the shortest appointments."""
        return 15 if duration_minutes < 30 else 30

    @staticmethod
    def _local(moment: datetime) -> datetime:
        """An aware business-time moment (a naive one is read as business time)."""
        tz = OpeningHoursCalendar.business_timezone()
        return moment.replace(tzinfo=tz) if moment.tzinfo is None else moment.astimezone(tz)

    @staticmethod
    def _opening_hours(assistant: AiAssistant) -> list[dict[str, str]] | None:
        """The business's opening-hour rows from its knowledge."""
        hours = (assistant.knowledge_json or {}).get("opening_hours")
        return hours if isinstance(hours, list) else None

    @staticmethod
    def _event_summary(request: AiAssistantRequest, type_label: str | None) -> str:
        """« Révision — Julie Roux » (« [Test] » first for an operator test)."""
        title = f"{type_label} — {request.name}" if type_label else f"Rendez-vous — {request.name}"
        return f"[Test] {title}" if request.is_test else title

    @staticmethod
    def _event_description(assistant: AiAssistant, request: AiAssistantRequest) -> str:
        """The event's notes: the contact, the need, who booked it."""
        lines = [f"Contact : {request.contact}"]
        need = (request.need or "").strip()
        if need:
            lines.append(f"Besoin : {need}")
        lines.append(f"Réservé par {assistant.assistant_name}, la réceptionniste du site.")
        return "\n".join(lines)

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


ai_assistant_calendar_service = AiAssistantCalendarService()
