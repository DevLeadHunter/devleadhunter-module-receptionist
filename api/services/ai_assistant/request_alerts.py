"""
Alerts to the business owner about the requests of their sold assistant: email, SMS, one reminder.

Once an assistant is sold, each request reaches its owner by email (every type) and, for the types
that cannot wait (quote, appointment, emergency by default), by a one-segment service SMS. During the
owner's quiet window (22 h → 8 h, Paris time, by default) the SMS waits for the end of the window.
A request still waiting after a day gets one reminder, never more; after two days the operator is
told, because a subscriber leaving requests unanswered is about to churn. A demo alerts no one but
the operator, whose push is sent by the follow-up (``request_follow_up``).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute, Session

from core.clock import naive_utc_now
from core.database import SessionLocal
from enums.ai_assistant_request import AiAssistantRequestStatus, AiAssistantRequestType
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.alert_settings import AlertSettings, QuietHours
from services.ai_assistant.alert_sms import AlertSms
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots
from services.ai_assistant.business_mailer import AiAssistantBusinessMailer
from services.ai_assistant.calendar_booking import ai_assistant_calendar_booking
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.message_delivery import AiAssistantMessageDelivery
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.request_analyzer import TranscriptLine, ai_assistant_request_analyzer
from services.ai_assistant.request_attachments import AiAssistantRequestAttachments
from services.ai_assistant.request_email import AiAssistantRequestEmail, RequestEmailContent
from services.ai_assistant.request_links import AiAssistantRequestLinks
from services.notification_service import notification_service
from services.sms.gsm_segments import to_strict_gsm7
from services.sms_config_service import sms_config_service

logger = logging.getLogger(__name__)

REMINDER_DELAY = timedelta(hours=24)
STALE_DELAY = timedelta(hours=48)
# Older requests are left alone, so switching the feature on never floods owners with old reminders.
REMINDER_WINDOW = timedelta(hours=72)
STALE_WINDOW = timedelta(days=7)
# A held SMS not sent within this delay (API down all morning, request reopened days later) is dropped.
SMS_DUE_WINDOW = timedelta(hours=12)


class AiAssistantRequestAlerts:
    """Sends the owner's alerts and reminders, and warns the operator about requests left waiting."""

    async def alert_owner(
        self,
        db: Session,
        request: AiAssistantRequest,
        assistant: AiAssistant,
        transcript: list[TranscriptLine],
        *,
        now: datetime | None = None,
    ) -> None:
        """
        Alert the owner of a sold assistant about a request just announced: email, then SMS.

        The request is marked alerted (the reminder and the 48 h warning follow from it) and its SMS
        planned before anything is sent: now, or at the end of the quiet window (the runner sends it).

        Args:
            db: Active database session (committed).
            request: The request, typed.
            assistant: Its assistant.
            transcript: The conversation, for the email.
            now: Current naive UTC time (tests); defaults to now.
        """
        if assistant.status != AiAssistantStatus.DELIVERED.value or AiAssistantBusinessMailer.is_muted(db, assistant):
            return
        settings = AlertSettings.of(assistant)
        current = now or naive_utc_now()
        request.owner_alerted_at = current
        text_now = False
        if settings.wants_sms(AiAssistantRequestType(request.type)):
            local = OpeningHoursCalendar.to_business_time(current)
            release = QuietHours.release_at(local, settings.quiet_start_hour, settings.quiet_end_hour)
            text_now = release == local
            request.sms_due_at = current if text_now else OpeningHoursCalendar.to_utc(release)
        db.commit()
        if settings.email_enabled:
            await self._email_owner(db, request, assistant, transcript, is_reminder=False)
        if text_now:
            await self._text_request(db, request, assistant, settings)

    async def send_due_sms(self, db: Session, *, now: datetime | None = None) -> int:
        """
        Send the SMS held during a quiet window, once it is over (requests handled since are skipped).

        Args:
            db: Active database session.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            How many SMS were sent.
        """
        current = now or naive_utc_now()
        rows = (
            db.query(AiAssistantRequest, AiAssistant)
            .join(AiAssistant, AiAssistant.id == AiAssistantRequest.assistant_id)
            .filter(
                AiAssistantRequest.sms_due_at <= current,
                AiAssistantRequest.sms_due_at >= current - SMS_DUE_WINDOW,
                AiAssistantRequest.sms_sent_at.is_(None),
                AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
                AiAssistantRequest.is_test.is_(False),
                AiAssistant.status == AiAssistantStatus.DELIVERED.value,
                AiAssistant.deleted_at.is_(None),
            )
            .order_by(AiAssistantRequest.id)
            .all()
        )
        sent = 0
        for request, assistant in rows:
            settings = AlertSettings.of(assistant)
            if settings.wants_sms(AiAssistantRequestType(request.type)) and not AiAssistantBusinessMailer.is_muted(
                db, assistant
            ):
                sent += int(await self._text_request(db, request, assistant, settings))
            else:
                # The owner turned this SMS off since it was held: drop it.
                request.sms_due_at = None
                db.commit()
        return sent

    async def send_reminders(self, db: Session, *, now: datetime | None = None) -> int:
        """
        Remind the owner, once, of each request still waiting a day after it came in.

        The reminder follows the alert rules (email, and SMS for the types worth one) and waits for
        the end of the quiet window.

        Args:
            db: Active database session.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            How many requests were reminded.
        """
        current = now or naive_utc_now()
        local = OpeningHoursCalendar.to_business_time(current)
        rows = (
            db.query(AiAssistantRequest, AiAssistant)
            .join(AiAssistant, AiAssistant.id == AiAssistantRequest.assistant_id)
            .filter(
                AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
                AiAssistantRequest.is_test.is_(False),
                AiAssistantRequest.owner_alerted_at.is_not(None),
                AiAssistantRequest.reminder_sent_at.is_(None),
                AiAssistantRequest.created_at <= current - REMINDER_DELAY,
                AiAssistantRequest.created_at >= current - REMINDER_WINDOW,
                AiAssistant.status == AiAssistantStatus.DELIVERED.value,
                AiAssistant.deleted_at.is_(None),
            )
            .order_by(AiAssistantRequest.id)
            .all()
        )
        reminded = 0
        for request, assistant in rows:
            settings = AlertSettings.of(assistant)
            if QuietHours.contains(local, settings.quiet_start_hour, settings.quiet_end_hour):
                continue
            if AiAssistantBusinessMailer.is_muted(db, assistant):
                continue
            if not self.claim(db, request, AiAssistantRequest.reminder_sent_at):
                continue
            reminded += 1
            request_type = AiAssistantRequestType(request.type)
            if settings.email_enabled:
                transcript = AiAssistantRequestAttachments.transcript(db, request)
                await self._email_owner(db, request, assistant, transcript, is_reminder=True)
            if settings.wants_sms(request_type) and settings.phone_e164 is not None:
                text = AlertSms.reminder(
                    request_type=request_type,
                    name=request.name,
                    contact=request.contact,
                    summary=request.need_summary or request.need,
                    received_local=OpeningHoursCalendar.to_business_time(request.created_at),
                    link=AiAssistantClientLinks.sms_link(assistant, request_id=request.id),
                    slots=self._sms_slots(db, request),
                )
                await self._send_sms(db, assistant, settings.phone_e164, text)
        return reminded

    async def notify_operator_of_waiting_requests(self, db: Session, *, now: datetime | None = None) -> int:
        """
        Tell the operator about subscribers' requests still waiting after 48 h, once per request.

        One push per subscriber, counting every request of theirs waiting for 48 h or more.

        Args:
            db: Active database session.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            How many requests were reported for the first time.
        """
        current = now or naive_utc_now()
        rows = (
            db.query(AiAssistantRequest, AiAssistant)
            .join(AiAssistant, AiAssistant.id == AiAssistantRequest.assistant_id)
            .filter(
                *self._waiting_filters(current),
                AiAssistantRequest.stale_notified_at.is_(None),
                AiAssistantRequest.created_at >= current - STALE_WINDOW,
            )
            .order_by(AiAssistantRequest.id)
            .all()
        )
        crossing: dict[int, list[AiAssistantRequest]] = defaultdict(list)
        assistants: dict[int, AiAssistant] = {}
        for request, assistant in rows:
            crossing[assistant.id].append(request)
            assistants[assistant.id] = assistant
        reported = 0
        for assistant_id, requests in crossing.items():
            claimed = sum(int(self.claim(db, request, AiAssistantRequest.stale_notified_at)) for request in requests)
            if not claimed:
                continue
            reported += claimed
            assistant = assistants[assistant_id]
            try:
                waiting_count = (
                    db.query(AiAssistantRequest.id)
                    .join(AiAssistant, AiAssistant.id == AiAssistantRequest.assistant_id)
                    .filter(*self._waiting_filters(current), AiAssistantRequest.assistant_id == assistant_id)
                    .count()
                )
                await notification_service.notify_assistant_requests_waiting(
                    db,
                    user_id=assistant.user_id,
                    prospect_id=assistant.prospect_id,
                    fallback_name=assistant.business_name,
                    waiting_count=waiting_count,
                )
            except Exception:
                logger.exception("Waiting-requests warning for assistant %s failed", assistant_id)
                db.rollback()
        return reported

    @staticmethod
    def _waiting_filters(current: datetime) -> tuple[ColumnElement[bool], ...]:
        """Real requests of a subscriber, alerted to its owner and still new 48 h later."""
        return (
            AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
            AiAssistantRequest.is_test.is_(False),
            AiAssistantRequest.owner_alerted_at.is_not(None),
            AiAssistantRequest.created_at <= current - STALE_DELAY,
            AiAssistant.status == AiAssistantStatus.DELIVERED.value,
            AiAssistant.deleted_at.is_(None),
        )

    async def send_test_sms(self, db: Session, assistant: AiAssistant) -> bool:
        """
        Text the alert mobile once, so the business sees where its alerts arrive.

        Args:
            db: Active database session.
            assistant: The sold assistant, its alert mobile set.

        Returns:
            True when the operator's SMS sender took the message.
        """
        phone = assistant.alert_phone_e164
        if not phone:
            return False
        text = to_strict_gsm7(
            f"Test de {assistant.assistant_name} pour {assistant.business_name} : vos alertes SMS arrivent bien ici."
        )
        return await self._send_sms(db, assistant, phone, text)

    async def run_pass(self) -> None:
        """One runner pass: held SMS, reminders, then the operator's 48 h warnings (a failing step skips alone)."""
        steps = (self.send_due_sms, self.send_reminders, self.notify_operator_of_waiting_requests)
        for step in steps:
            db = SessionLocal()
            try:
                await step(db)
            except Exception:
                logger.exception("Assistant alert step %s failed", step.__name__)
                db.rollback()
            finally:
                db.close()

    async def _text_request(
        self, db: Session, request: AiAssistantRequest, assistant: AiAssistant, settings: AlertSettings
    ) -> bool:
        """Send the request's alert SMS if nobody did yet; returns whether this call sent it."""
        if settings.phone_e164 is None or not self.claim(db, request, AiAssistantRequest.sms_sent_at):
            return False
        text = AlertSms.new_request(
            request_type=AiAssistantRequestType(request.type),
            name=request.name,
            contact=request.contact,
            summary=request.need_summary or request.need,
            has_photos=bool(AiAssistantRequestAttachments.photo_urls(request)),
            link=AiAssistantClientLinks.sms_link(assistant, request_id=request.id),
            slots=tuple(AiAssistantAppointmentSlots.short_labels(request.appointment_slots_json)),
            booked=ai_assistant_calendar_booking.booked_labels(db, [request.id]).get(request.id),
        )
        return await self._send_sms(db, assistant, settings.phone_e164, text)

    @staticmethod
    def _sms_slots(db: Session, request: AiAssistantRequest) -> tuple[str, ...]:
        """What a reminder SMS says of the appointment: the booked slot, else the wished half-days."""
        booked = ai_assistant_calendar_booking.booked_labels(db, [request.id]).get(request.id)
        if booked:
            return (booked,)
        return tuple(AiAssistantAppointmentSlots.short_labels(request.appointment_slots_json))

    @staticmethod
    async def _send_sms(db: Session, assistant: AiAssistant, phone_e164: str, text: str) -> bool:
        """Text the owner through the operator's SMS sender; logs why when it cannot."""
        config = sms_config_service.get(db, assistant.user_id)
        if config is None or not config.sender:
            AiAssistantRequestAlerts._log_sms_refusal(
                assistant, "Aucun nom d'expéditeur SMS : Paramètres → Relance SMS."
            )
            return False
        outcome = await AiAssistantMessageDelivery.send_service_sms(
            db,
            assistant,
            config,
            to_e164=phone_e164,
            text=text,
            recipient_name=f"{assistant.business_name} (alertes)",
            log_label=f"Alert SMS to assistant {assistant.id} owner",
        )
        if outcome is None:
            return False
        # A provider failure is already notified by the SMS service; a refusal before it is not.
        if not outcome.sent and outcome.message is None:
            AiAssistantRequestAlerts._log_sms_refusal(assistant, outcome.reason or "Refusé avant l'envoi.")
        return outcome.sent

    @staticmethod
    def _log_sms_refusal(assistant: AiAssistant, reason: str) -> None:
        """Record in the activity log why an owner alert SMS did not leave (it is not retried)."""
        logger.warning("Alert SMS to assistant %s owner not sent: %s", assistant.id, reason)
        AiAssistantMessageDelivery.record_warning(
            assistant, action="assistant_alert_sms_skipped", title="SMS d'alerte non envoyé", detail=reason
        )

    async def _email_owner(
        self,
        db: Session,
        request: AiAssistantRequest,
        assistant: AiAssistant,
        transcript: list[TranscriptLine],
        *,
        is_reminder: bool,
    ) -> None:
        """Send the request summary (or its reminder) to the business, from the operator's identity; never raises."""
        try:
            recipient = AiAssistantBusinessMailer.business_email(db, assistant)
            if not recipient:
                logger.info("Assistant %s: no business email for request %s", assistant.id, request.id)
                if not AiAssistantBusinessMailer.is_muted(db, assistant):
                    self._log_email_failure(assistant, request, "aucune adresse email pour ce commerce")
                return
            rendered = AiAssistantRequestEmail.render(
                RequestEmailContent(
                    business_name=assistant.business_name,
                    assistant_name=assistant.assistant_name,
                    persona_gender=ai_assistant_config_builder.resolve_persona_gender(assistant.assistant_name),
                    request_type=AiAssistantRequestType(request.type),
                    visitor_name=request.name,
                    contact=request.contact,
                    need=request.need,
                    need_summary=request.need_summary,
                    received_at=OpeningHoursCalendar.to_business_time(request.created_at),
                    received_outside_hours=request.received_outside_hours,
                    transcript=ai_assistant_request_analyzer.bound_transcript(transcript),
                    handled_url=AiAssistantRequestLinks.handled_url(request.id),
                    photo_urls=tuple(AiAssistantRequestAttachments.photo_urls(request)),
                    is_reminder=is_reminder,
                    client_space_url=AiAssistantClientLinks.url(assistant, request_id=request.id),
                    appointment_slots=tuple(AiAssistantAppointmentSlots.labels(request.appointment_slots_json)),
                    appointment_booked=ai_assistant_calendar_booking.booked_labels(db, [request.id]).get(request.id),
                )
            )
        except Exception:
            logger.warning("Request %s email could not be written", request.id, exc_info=True)
            db.rollback()
            return
        failure = await AiAssistantBusinessMailer.send(
            db, assistant, rendered, recipient=recipient, recipient_name=assistant.business_name
        )
        if failure is not None:
            logger.warning("Request %s email failed: %s", request.id, failure)
            self._log_email_failure(assistant, request, failure)

    @staticmethod
    def _log_email_failure(assistant: AiAssistant, request: AiAssistantRequest, reason: str) -> None:
        """Record in the activity log that a request's email did not reach the business (the reminder retries)."""
        AiAssistantMessageDelivery.record_warning(
            assistant,
            action="assistant_alert_email_failed",
            title="email de demande non envoyé",
            detail=f"Demande {request.id} : {reason}",
        )

    @staticmethod
    def claim(db: Session, request: AiAssistantRequest, column: InstrumentedAttribute[datetime | None]) -> bool:
        """
        Atomically stamp a one-shot timestamp of a request still new, so concurrent passes act on it once.

        Requiring ``new`` in the same statement closes the gap between a pass loading its rows and
        acting on them: a request handled meanwhile is left alone.

        Args:
            db: Active database session (committed).
            request: The request (refreshed).
            column: Its one-shot column (``owner_notified_at``, ``sms_sent_at``…).

        Returns:
            True when this call stamped it, False when someone already had or it is no longer new.
        """
        return AiAssistantMessageDelivery.claim(
            db,
            request,
            AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
            column.is_(None),
            values={column: naive_utc_now()},
        )


ai_assistant_request_alerts = AiAssistantRequestAlerts()
