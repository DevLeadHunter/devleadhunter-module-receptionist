"""
Booking a visitor's pick in a client's Google agenda, and the appointments booked as the business reads them.

Bookings of one agenda run one at a time (an in-process lock; the API runs one worker) and no database lock nor open
write is held while Google answers. Without a usable agenda the pick is kept as a wished half-day, which the business
confirms.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import ClassVar

from sqlalchemy.orm import Session

from core.config import settings
from enums.ai_assistant_request import AiAssistantDayPeriod, AiAssistantRequestType
from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_calendar import AiAssistantCalendar
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots, AppointmentRefused, AppointmentSlot
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.calendar_access import ai_assistant_calendar_access
from services.ai_assistant.calendar_settings import CalendarSettings
from services.ai_assistant.calendar_slot_grid import AiAssistantCalendarSlotGrid
from services.ai_assistant.google_calendar_client import (
    CalendarEventDraft,
    CalendarEventState,
    GoogleCalendarError,
    google_calendar_client,
)
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.request_email import AiAssistantRequestEmail
from services.french_date_formatter import FrenchDateFormatter
from services.sms.phone_normalizer import to_served_mobile

logger = logging.getLogger(__name__)


class SlotTakenError(Exception):
    """The slot is no longer free: booked in between, or busy in the agenda."""


class DailyBookingCapReached(Exception):
    """The assistant booked as many appointments as a day allows: the pick is kept as a wish."""


@dataclass(frozen=True)
class BookingOutcome:
    """A visitor's pick: the appointment created in the agenda, or None when it was kept as a wished half-day."""

    appointment: AiAssistantAppointment | None


class AiAssistantCalendarBooking:
    """Books a visitor's pick in the agenda and reads the appointments booked."""

    REMINDER_HOURS_BEFORE: ClassVar[int] = 24
    # The reminder never leaves before 9:00 nor after 19:00 (business time).
    REMINDER_EARLIEST: ClassVar[time] = time(9, 0)
    REMINDER_LATEST: ClassVar[time] = time(19, 0)
    REMINDER_MIN_GAP: ClassVar[timedelta] = timedelta(hours=2)
    MAX_BOOKINGS_PER_DAY: ClassVar[int] = 20

    def __init__(self) -> None:
        # One booking at a time per agenda (the API runs a single worker).
        self._locks: dict[int, asyncio.Lock] = {}

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
        local_now = OpeningHoursCalendar.localize(now or OpeningHoursCalendar.business_now())
        calendar = ai_assistant_calendar_access.usable_calendar(db, assistant)
        if calendar is not None:
            phone, email = self.visitor_channels(db, assistant, request.contact)
            if self._has_upcoming_appointment(db, assistant, phone=phone, email=email, except_request_id=request.id):
                raise AppointmentRefused(
                    "Un rendez-vous est déjà réservé avec ce contact. Pour le modifier, appelez directement le commerce."
                )
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
            except DailyBookingCapReached:
                # Past the cap (a script, a flood), picks become wishes and no message leaves for a visitor.
                logger.warning("Assistant %s reached %s bookings in 24 h", assistant.id, self.MAX_BOOKINGS_PER_DAY)
            except GoogleCalendarError:
                logger.warning("Booking of request %s falls back on a wished half-day", request.id)
            else:
                self._mark_appointment(request)
                db.commit()
                return BookingOutcome(appointment=appointment)

        local_start = OpeningHoursCalendar.localize(start)
        period = (
            AiAssistantDayPeriod.MORNING
            if AiAssistantCalendarSlotGrid.is_morning(local_start)
            else AiAssistantDayPeriod.AFTERNOON
        )
        # The wished half-day obeys the same rules as one picked in the half-day panel (open day, from tomorrow).
        wished = AiAssistantAppointmentSlots.check(
            AiAssistantAppointmentSlots.opening_hours_of(assistant),
            [AppointmentSlot(day=local_start.date(), period=period)],
            today=local_now.date(),
        )
        request.appointment_slots_json = AiAssistantAppointmentSlots.to_json(wished)
        self._mark_appointment(request)
        db.commit()
        return BookingOutcome(appointment=None)

    @staticmethod
    def _has_upcoming_appointment(
        db: Session, assistant: AiAssistant, *, phone: str | None, email: str | None, except_request_id: int
    ) -> bool:
        """Whether this contact already holds a future appointment with the assistant (one at a time per contact)."""
        if phone is None and email is None:
            return False
        contact_filter = (
            AiAssistantAppointment.visitor_phone_e164 == phone
            if phone is not None
            else AiAssistantAppointment.visitor_email == email
        )
        now_utc = datetime.now(UTC).replace(tzinfo=None)
        return (
            db.query(AiAssistantAppointment.id)
            .filter(
                AiAssistantAppointment.assistant_id == assistant.id,
                AiAssistantAppointment.request_id != except_request_id,
                AiAssistantAppointment.ends_at > now_utc,
                contact_filter,
            )
            .first()
            is not None
        )

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
        if AiAssistantRequestEmail.is_email(cleaned):
            return None, cleaned.lower()[:255]
        return to_served_mobile(cleaned, country=ai_assistant_service.business_country(db, assistant)), None

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

        The event is created first, with an id derived from the request and the slot (a repeated insert finds it),
        then the appointment is saved in one short transaction.

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
        local_now = OpeningHoursCalendar.localize(now or OpeningHoursCalendar.business_now())
        booking_settings = CalendarSettings.of(calendar)
        local_start = OpeningHoursCalendar.localize(start)
        duration = timedelta(minutes=booking_settings.duration_minutes)
        chosen_type = self._check_type(booking_settings, type_label)
        AiAssistantCalendarSlotGrid.check_start(
            AiAssistantAppointmentSlots.opening_hours_of(assistant), booking_settings, local_start, local_now
        )
        start_utc = OpeningHoursCalendar.to_utc(local_start)
        end_utc = start_utc + duration

        async with self._lock_for(calendar.id):
            # A fresh transaction: the checks below see the bookings committed a moment ago.
            db.commit()
            if self._bookings_today(db, assistant, local_now) >= self.MAX_BOOKINGS_PER_DAY:
                raise DailyBookingCapReached()
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
            calendar_id = booking_settings.calendar_id
            event_id = self._event_id(request.id, start_utc)
            try:
                busy = await ai_assistant_calendar_access.with_fresh_token(
                    db,
                    calendar,
                    lambda token: google_calendar_client.busy_periods(token, calendar_id, start=start_utc, end=end_utc),
                )
            except GoogleCalendarError as exc:
                ai_assistant_calendar_access.record_failure(db, assistant, calendar, exc)
                raise
            if taken is not None:
                ai_assistant_calendar_access.forget_busy(calendar.id)
                raise SlotTakenError("Ce créneau vient d'être pris")
            already_created = False
            if AiAssistantCalendarSlotGrid.overlaps(busy, local_start, local_start + duration):
                # The busy stretch may be our own event, created before a lost answer or a failed write of the row.
                own_event = await self._own_event(db, calendar, calendar_id, event_id)
                if own_event is None:
                    ai_assistant_calendar_access.forget_busy(calendar.id)
                    raise SlotTakenError("Ce créneau vient d'être pris")
                already_created = True

            if not already_created:
                draft = CalendarEventDraft(
                    event_id=event_id,
                    summary=self._event_summary(request, chosen_type),
                    description=self._event_description(assistant, request),
                    start=local_start,
                    end=local_start + duration,
                    time_zone=getattr(tz, "key", "UTC"),
                    request_id=request.id,
                )
                try:
                    event_id = await ai_assistant_calendar_access.with_fresh_token(
                        db, calendar, lambda token: self._insert_event(token, calendar_id, draft)
                    )
                except GoogleCalendarError as exc:
                    ai_assistant_calendar_access.record_failure(db, assistant, calendar, exc)
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
                reminder_due_at=self.reminder_due_at(start_utc, booked_at=OpeningHoursCalendar.to_utc(local_now)),
            )
            db.add(appointment)
            if calendar.last_error:
                calendar.last_error = None
            db.commit()
            db.refresh(appointment)
        ai_assistant_calendar_access.forget_busy(calendar.id)
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
        due_utc = OpeningHoursCalendar.to_utc(due)
        return due_utc if due_utc > booked_at + cls.REMINDER_MIN_GAP else None

    @staticmethod
    def start_label(appointment: AiAssistantAppointment) -> str:
        """An appointment's start for the business (« mar. 29/09 à 14:30 »)."""
        return FrenchDateFormatter.short_date_time(OpeningHoursCalendar.to_business_time(appointment.starts_at))

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

    def _lock_for(self, calendar_id: int) -> asyncio.Lock:
        """The lock that makes one agenda's bookings run one at a time."""
        return self._locks.setdefault(calendar_id, asyncio.Lock())

    @staticmethod
    async def _own_event(
        db: Session, calendar: AiAssistantCalendar, calendar_id: str, event_id: str
    ) -> CalendarEventState | None:
        """The event this booking would create, when a previous attempt already created it and it still stands."""
        try:
            state = await ai_assistant_calendar_access.with_fresh_token(
                db, calendar, lambda token: google_calendar_client.get_event(token, calendar_id, event_id)
            )
        except GoogleCalendarError:
            return None
        return state if state is not None and not state.cancelled else None

    @staticmethod
    def _event_id(request_id: int, start_utc: datetime) -> str:
        """Our id of the Google event of a request's slot: the same request and slot always give the same id."""
        message = f"assistant-event:{request_id}:{start_utc.isoformat()}".encode()
        digest = hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()[:26]
        # Google accepts the letters a to v and digits: hexadecimal fits.
        return f"dlh{digest}"

    # Pauses before the second and third attempt at creating the event, after a lost answer, a 5xx or a 429.
    INSERT_RETRY_DELAYS: ClassVar[tuple[float, ...]] = (1.0, 3.0)

    @classmethod
    async def _insert_event(cls, access_token: str, calendar_id: str, draft: CalendarEventDraft) -> str:
        """Create the event, again after a lost answer, a Google outage or a rate limit (the id makes it harmless)."""
        for delay in (*cls.INSERT_RETRY_DELAYS, None):
            try:
                return await google_calendar_client.insert_event(access_token, calendar_id, draft)
            except GoogleCalendarError as exc:
                retryable = exc.status_code is None or exc.status_code == 429 or exc.status_code >= 500
                if not retryable or delay is None:
                    raise
                await asyncio.sleep(delay)
        raise GoogleCalendarError("Google Agenda injoignable")

    @staticmethod
    def _bookings_today(db: Session, assistant: AiAssistant, local_now: datetime) -> int:
        """How many appointments the assistant booked over the last 24 hours."""
        since = OpeningHoursCalendar.to_utc(local_now) - timedelta(days=1)
        return (
            db.query(AiAssistantAppointment)
            .filter(AiAssistantAppointment.assistant_id == assistant.id, AiAssistantAppointment.created_at >= since)
            .count()
        )

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


ai_assistant_calendar_booking = AiAssistantCalendarBooking()
