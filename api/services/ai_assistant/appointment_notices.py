"""
What a visitor receives once their appointment is booked: the confirmation, then the J-1 reminder.

Texts follow the widget language (``appointment_texts``). The SMS is one GSM-7 segment sent as a service message
through the operator's SMS sender (``kind = service``, the STOP list honoured); the email leaves from the owner's
sending identity, transactional, with the appointment as an ``.ics`` file. The visitor is told to call the
business, never to answer the email (it would reach the operator). Each message is claimed on the appointment row
before it leaves: never twice.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, time, timedelta
from typing import ClassVar

from sqlalchemy.orm import InstrumentedAttribute, Session

from core.database import SessionLocal
from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from services.ai_assistant.appointment_texts import AppointmentTexts, BusinessCard
from services.ai_assistant.calendar_access import ai_assistant_calendar_access
from services.ai_assistant.calendar_settings import CalendarSettings
from services.ai_assistant.google_calendar_client import GoogleCalendarError, google_calendar_client
from services.ai_assistant.message_delivery import AiAssistantMessageDelivery
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.email_attachment import EmailAttachment
from services.email_sending_service import EmailSendingService
from services.sms_config_service import sms_config_service

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Current time, naive UTC (patched in tests)."""
    return datetime.now(UTC).replace(tzinfo=None)


class AiAssistantAppointmentNotices:
    """Sends the visitors' confirmations and J-1 reminders."""

    # A lost confirmation is picked up within a day; a reminder no later than an hour before the start.
    CONFIRMATION_GRACE: ClassVar[timedelta] = timedelta(minutes=2)
    CONFIRMATION_MAX_AGE: ClassVar[timedelta] = timedelta(days=1)
    REMINDER_CUTOFF: ClassVar[timedelta] = timedelta(hours=1)
    # A reminder leaves the day before, between 9:00 and 20:00 (business time), never at night.
    REMINDER_FROM: ClassVar[time] = time(9, 0)
    REMINDER_UNTIL: ClassVar[time] = time(20, 0)

    def __init__(self) -> None:
        self._background_tasks: set[asyncio.Task[None]] = set()

    def schedule_confirmation(self, appointment_id: int) -> None:
        """
        Send the visitor's confirmation in the background, without delaying the widget.

        Args:
            appointment_id: The appointment just booked.
        """
        task = asyncio.create_task(self._confirm_in_background(appointment_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def send_confirmation(self, db: Session, appointment: AiAssistantAppointment) -> bool:
        """
        Confirm an appointment to its visitor (SMS to a mobile, email to an address), once.

        Args:
            db: Active database session.
            appointment: The booked appointment.

        Returns:
            True when this call claimed the confirmation (whatever the channels' outcome).
        """
        if not self._claim(db, appointment, AiAssistantAppointment.confirmation_sent_at):
            return False
        assistant = db.get(AiAssistant, appointment.assistant_id)
        if assistant is None:
            return True
        card = BusinessCard.of(assistant)
        language = AppointmentTexts.language(appointment.language)
        start_local = OpeningHoursCalendar.to_business_time(appointment.starts_at)
        if appointment.visitor_phone_e164:
            text = AppointmentTexts.confirmation_sms(
                card=card, start_local=start_local, type_label=appointment.type_label, language=language
            )
            await self._send_sms(db, assistant, appointment, text)
        if appointment.visitor_email:
            await self._send_email(db, assistant, appointment, card, language, start_local)
        if not appointment.visitor_phone_e164 and not appointment.visitor_email:
            self._log_failure(
                assistant,
                appointment,
                "Ni mobile (de France, Belgique, Luxembourg, Suisse ou Allemagne) ni email : pas de confirmation.",
            )
        return True

    async def send_reminder(
        self, db: Session, appointment: AiAssistantAppointment, *, now: datetime | None = None
    ) -> bool:
        """
        Remind the visitor the day before (SMS; by email when they left no mobile), once.

        Args:
            db: Active database session.
            appointment: The booked appointment.
            now: Current time, naive UTC (tests); defaults to now.

        Returns:
            True when this call claimed the reminder.
        """
        if not self._claim(db, appointment, AiAssistantAppointment.reminder_sent_at):
            return False
        assistant = db.get(AiAssistant, appointment.assistant_id)
        if assistant is None:
            return True
        if not await self._still_scheduled(db, assistant, appointment, now=now or _utc_now()):
            return True
        card = BusinessCard.of(assistant)
        language = AppointmentTexts.language(appointment.language)
        start_local = OpeningHoursCalendar.to_business_time(appointment.starts_at)
        if appointment.visitor_phone_e164:
            await self._send_sms(
                db,
                assistant,
                appointment,
                AppointmentTexts.reminder_sms(card=card, start_local=start_local, language=language),
            )
        elif appointment.visitor_email:
            await self._send_email(db, assistant, appointment, card, language, start_local, is_reminder=True)
        return True

    @staticmethod
    async def _still_scheduled(
        db: Session, assistant: AiAssistant, appointment: AiAssistantAppointment, *, now: datetime
    ) -> bool:
        """
        Whether the event still stands in the agenda for tomorrow, read from Google before the reminder leaves.

        A cancelled or deleted event drops the reminder; an event the business moved updates the row, and the
        reminder leaves only if the new day is still tomorrow. An agenda that cannot be read leaves it as stored.

        Args:
            db: Active database session.
            assistant: The assistant.
            appointment: The appointment whose reminder is due.
            now: Current time, naive UTC.
        """
        calendar = ai_assistant_calendar_access.calendar_of(db, assistant)
        if calendar is None or not appointment.google_event_id:
            return True
        calendar_id = CalendarSettings.of(calendar).calendar_id
        event_id = appointment.google_event_id
        try:
            state = await ai_assistant_calendar_access.with_fresh_token(
                db, calendar, lambda token: google_calendar_client.get_event(token, calendar_id, event_id)
            )
        except GoogleCalendarError:
            logger.warning("Appointment %s: agenda unreadable before the reminder, sent as stored", appointment.id)
            return True
        if state is None or state.cancelled:
            AiAssistantAppointmentNotices._log_failure(
                assistant, appointment, "Rappel non envoyé : le rendez-vous n'est plus dans l'agenda."
            )
            return False
        if state.start is not None and state.start != appointment.starts_at:
            duration = appointment.ends_at - appointment.starts_at
            appointment.starts_at = state.start
            appointment.ends_at = state.start + duration
            db.commit()
            tomorrow = OpeningHoursCalendar.to_business_time(now).date() + timedelta(days=1)
            if OpeningHoursCalendar.to_business_time(state.start).date() != tomorrow:
                AiAssistantAppointmentNotices._log_failure(
                    assistant, appointment, "Rappel non envoyé : le rendez-vous a été déplacé à une autre date."
                )
                return False
        return True

    async def run_pass(self, db: Session, *, now: datetime | None = None) -> int:
        """
        Send the confirmations a restart lost and the reminders that are due.

        Args:
            db: Active database session.
            now: Current time, naive UTC (tests); defaults to now.

        Returns:
            How many messages were claimed.
        """
        current = now or _utc_now()
        booked = AiAssistantAppointment.google_event_id.isnot(None)
        lost = (
            db.query(AiAssistantAppointment)
            .filter(
                booked,
                AiAssistantAppointment.confirmation_sent_at.is_(None),
                AiAssistantAppointment.created_at <= current - self.CONFIRMATION_GRACE,
                AiAssistantAppointment.created_at >= current - self.CONFIRMATION_MAX_AGE,
                AiAssistantAppointment.starts_at > current,
            )
            .all()
        )
        due = (
            db.query(AiAssistantAppointment)
            .filter(
                booked,
                AiAssistantAppointment.reminder_sent_at.is_(None),
                AiAssistantAppointment.reminder_due_at.isnot(None),
                AiAssistantAppointment.reminder_due_at <= current,
                AiAssistantAppointment.starts_at > current + self.REMINDER_CUTOFF,
            )
            .all()
        )
        claimed = 0
        for appointment in lost:
            claimed += int(await self.send_confirmation(db, appointment))
        local_now = OpeningHoursCalendar.to_business_time(current)
        for appointment in due:
            start_local = OpeningHoursCalendar.to_business_time(appointment.starts_at)
            if local_now.date() != start_local.date() - timedelta(days=1):
                # No longer the day before (the runner was stopped): « demain » would be wrong, it is dropped.
                appointment.reminder_due_at = None
                db.commit()
                continue
            if not self.REMINDER_FROM <= local_now.time().replace(tzinfo=None) < self.REMINDER_UNTIL:
                continue
            claimed += int(await self.send_reminder(db, appointment, now=current))
        return claimed

    async def run_pass_in_background(self) -> None:
        """One pass on a fresh session; never raises (called by the requests runner)."""
        db = SessionLocal()
        try:
            await self.run_pass(db)
        except Exception:
            logger.exception("Appointment notices pass failed")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    def _claim(
        db: Session, appointment: AiAssistantAppointment, column: InstrumentedAttribute[datetime | None]
    ) -> bool:
        """Mark a message sent before it leaves, only if nobody did (atomic)."""
        return AiAssistantMessageDelivery.claim(db, appointment, column.is_(None), values={column: _utc_now()})

    @staticmethod
    async def _send_sms(db: Session, assistant: AiAssistant, appointment: AiAssistantAppointment, text: str) -> None:
        """Text the visitor through the operator's SMS sender; logs why when it cannot."""
        config = sms_config_service.get(db, assistant.user_id)
        reason = "Aucune configuration SMS" if config is None else None
        if config is not None:
            outcome = await AiAssistantMessageDelivery.send_service_sms(
                db,
                assistant,
                config,
                to_e164=appointment.visitor_phone_e164 or "",
                text=text,
                recipient_name=f"Rendez-vous {assistant.business_name}",
                log_label=f"Appointment {appointment.id} SMS",
            )
            if outcome is None:
                reason = "Erreur d'envoi"
            elif not outcome.sent:
                reason = outcome.reason
        if reason:
            AiAssistantAppointmentNotices._log_failure(assistant, appointment, f"SMS non envoyé : {reason}")

    @staticmethod
    async def _send_email(
        db: Session,
        assistant: AiAssistant,
        appointment: AiAssistantAppointment,
        card: BusinessCard,
        language: str,
        start_local: datetime,
        is_reminder: bool = False,
    ) -> None:
        """Email the visitor the confirmation (or the reminder) and its .ics file; logs why when it cannot."""
        rendered = AppointmentTexts.email(
            card=card,
            start_local=start_local,
            duration_minutes=int((appointment.ends_at - appointment.starts_at).total_seconds() // 60),
            type_label=appointment.type_label,
            language=language,
            is_reminder=is_reminder,
        )
        try:
            result = await EmailSendingService(db).send_via_user_identity(
                user_id=assistant.user_id,
                recipient_email=appointment.visitor_email or "",
                subject=rendered.subject,
                body_html=rendered.html,
                attachments=[
                    EmailAttachment(
                        filename="rendez-vous.ics",
                        content=AppointmentTexts.ics(card=card, appointment=appointment, language=language),
                        content_type="text/calendar",
                    )
                ],
                is_transactional=True,
            )
        except Exception:
            logger.warning("Appointment %s email failed", appointment.id, exc_info=True)
            db.rollback()
            result = {"success": False, "error": "Erreur d'envoi"}
        if not (result or {}).get("success"):
            AiAssistantAppointmentNotices._log_failure(
                assistant, appointment, f"Email non envoyé : {(result or {}).get('error') or 'refusé'}"
            )

    @staticmethod
    def _log_failure(assistant: AiAssistant, appointment: AiAssistantAppointment, detail: str) -> None:
        """Tell the owner a visitor was not told (activity log)."""
        AiAssistantMessageDelivery.record_warning(
            assistant,
            action="assistant_appointment_notice_failed",
            title=f"rendez-vous {appointment.id} : visiteur non prévenu",
            detail=detail,
        )

    async def _confirm_in_background(self, appointment_id: int) -> None:
        """Run :meth:`send_confirmation` on a fresh session; never raises."""
        db = SessionLocal()
        try:
            appointment = db.get(AiAssistantAppointment, appointment_id)
            if appointment is not None:
                await self.send_confirmation(db, appointment)
        except Exception:
            logger.exception("Appointment %s confirmation failed", appointment_id)
            db.rollback()
        finally:
            db.close()


ai_assistant_appointment_notices = AiAssistantAppointmentNotices()
