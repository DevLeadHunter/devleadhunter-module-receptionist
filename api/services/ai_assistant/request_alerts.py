"""
Alerts to the business owner about the requests of their sold assistant: email, SMS, one reminder.

Once an assistant is sold, each request reaches its owner by email (every type) and, for the types
that cannot wait (quote, appointment, emergency by default), by a one-segment service SMS. During the
owner's quiet window (22 h → 8 h, Paris time, by default) the SMS waits for the end of the window.
A request still waiting after a day gets one reminder, never more; after two days the operator is
told, because a subscriber leaving requests unanswered is about to churn. A demo alerts no one but
the operator, whose push is sent by the request service.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute, Session

from core.database import SessionLocal
from enums.ai_assistant_request import AiAssistantRequestStatus, AiAssistantRequestType
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_request import AiAssistantRequest
from services.activity_log_service import CATEGORY_ASSISTANT, STATUS_WARNING, activity_log_service
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots
from services.ai_assistant.business_mailer import AiAssistantBusinessMailer
from services.ai_assistant.calendar_booking import ai_assistant_calendar_booking
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.request_analyzer import TranscriptLine, ai_assistant_request_analyzer
from services.ai_assistant.request_email import AiAssistantRequestEmail, RequestEmailContent
from services.ai_assistant.request_links import AiAssistantRequestLinks
from services.notification_service import notification_service
from services.sms.gsm_segments import segment_count, to_strict_gsm7
from services.sms_config_service import sms_config_service
from services.sms_service import sms_service

logger = logging.getLogger(__name__)

DEFAULT_SMS_TYPES: frozenset[AiAssistantRequestType] = frozenset(
    {AiAssistantRequestType.QUOTE, AiAssistantRequestType.APPOINTMENT, AiAssistantRequestType.URGENT}
)
DEFAULT_QUIET_START_HOUR = 22
DEFAULT_QUIET_END_HOUR = 8
REMINDER_DELAY = timedelta(hours=24)
STALE_DELAY = timedelta(hours=48)
# Older requests are left alone, so switching the feature on never floods owners with old reminders.
REMINDER_WINDOW = timedelta(hours=72)
STALE_WINDOW = timedelta(days=7)
# A held SMS not sent within this delay (API down all morning, request reopened days later) is dropped.
SMS_DUE_WINDOW = timedelta(hours=12)


def _utc_now() -> datetime:
    """Current time as naive UTC, the storage convention."""
    return datetime.now(UTC).replace(tzinfo=None)


_REQUEST_TYPE_VALUES: frozenset[str] = frozenset(request_type.value for request_type in AiAssistantRequestType)


def _hour_or(value: int | None, default: int) -> int:
    """A stored hour when it is a valid one (0-23), else the default."""
    return value if isinstance(value, int) and 0 <= value <= 23 else default


@dataclass(frozen=True)
class AlertSettings:
    """An assistant's alert settings with the defaults applied."""

    phone_e164: str | None
    sms_enabled: bool
    email_enabled: bool
    sms_types: frozenset[AiAssistantRequestType]
    quiet_start_hour: int
    quiet_end_hour: int

    @classmethod
    def of(cls, assistant: AiAssistant) -> AlertSettings:
        """
        Read an assistant's alert settings, a NULL column meaning its default.

        Args:
            assistant: The assistant.

        Returns:
            The effective settings.
        """
        stored_types = assistant.alert_sms_types
        sms_types = (
            frozenset(AiAssistantRequestType(value) for value in stored_types if value in _REQUEST_TYPE_VALUES)
            if isinstance(stored_types, list)
            else DEFAULT_SMS_TYPES
        )
        return cls(
            phone_e164=assistant.alert_phone_e164 or None,
            sms_enabled=assistant.alert_sms_enabled is not False,
            email_enabled=assistant.alert_email_enabled is not False,
            sms_types=sms_types,
            quiet_start_hour=_hour_or(assistant.alert_quiet_start_hour, DEFAULT_QUIET_START_HOUR),
            quiet_end_hour=_hour_or(assistant.alert_quiet_end_hour, DEFAULT_QUIET_END_HOUR),
        )

    def wants_sms(self, request_type: AiAssistantRequestType) -> bool:
        """
        Whether a request of this type is texted to the owner.

        Args:
            request_type: The request type.

        Returns:
            True when SMS are on, a number is set and the type is one worth an SMS.
        """
        return self.sms_enabled and self.phone_e164 is not None and request_type in self.sms_types


class QuietHours:
    """The owner's « do not disturb » window, in the business's local time (hours 0-23)."""

    @staticmethod
    def contains(local: datetime, start_hour: int, end_hour: int) -> bool:
        """
        Whether a local moment falls in the window.

        Args:
            local: Local time of the business.
            start_hour: First quiet hour (22 for 22:00).
            end_hour: Hour the window ends (8 for 08:00); equal to ``start_hour`` = no window.

        Returns:
            True inside the window.
        """
        if start_hour == end_hour:
            return False
        if start_hour < end_hour:
            return start_hour <= local.hour < end_hour
        return local.hour >= start_hour or local.hour < end_hour

    @classmethod
    def release_at(cls, local: datetime, start_hour: int, end_hour: int) -> datetime:
        """
        The first moment at or after ``local`` outside the window.

        Args:
            local: Local time of the business.
            start_hour: First quiet hour.
            end_hour: Hour the window ends.

        Returns:
            ``local`` itself outside the window, else the window's end (local time).
        """
        if not cls.contains(local, start_hour, end_hour):
            return local
        release = local.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        return release if release > local else release + timedelta(days=1)


class AlertSms:
    """Writes the owner's SMS: one GSM-7 segment, the summary cut to fit, then the client-space link."""

    LABELS: ClassVar[dict[AiAssistantRequestType, str]] = {
        AiAssistantRequestType.QUESTION: "Nouvelle question",
        AiAssistantRequestType.QUOTE: "Nouvelle demande de devis",
        AiAssistantRequestType.APPOINTMENT: "Nouvelle demande de RDV",
        AiAssistantRequestType.URGENT: "URGENT, nouvelle demande",
        AiAssistantRequestType.OTHER: "Nouvelle demande",
    }
    REMINDER_LABELS: ClassVar[dict[AiAssistantRequestType, str]] = {
        AiAssistantRequestType.QUESTION: "question",
        AiAssistantRequestType.QUOTE: "demande de devis",
        AiAssistantRequestType.APPOINTMENT: "demande de RDV",
        AiAssistantRequestType.URGENT: "demande urgente",
        AiAssistantRequestType.OTHER: "demande",
    }
    # The contact is what the owner acts on: kept whole up to 60 characters, the name is cut first.
    _NAME_MAX_CHARS = 30
    _CONTACT_MAX_CHARS = 60
    # The summary comes before the client-space link: the link goes when it would leave less than this.
    _MIN_SUMMARY_WITH_LINK = 30
    # The shorter name tried before giving up the second wished half-day.
    _SHORT_NAME_MAX_CHARS = 15

    @classmethod
    def new_request(
        cls,
        *,
        request_type: AiAssistantRequestType,
        name: str,
        contact: str,
        summary: str | None,
        has_photos: bool,
        link: str | None = None,
        slots: tuple[str, ...] = (),
        booked: str | None = None,
    ) -> str:
        """
        The SMS announcing a request (« Nouvelle demande de devis (photo) de Marc, 06… : … Suivi : … »).

        Args:
            request_type: Its type.
            name: The visitor's name.
            contact: Their phone or email.
            summary: What they need.
            has_photos: Whether they sent photos.
            link: The client space, without scheme; dropped when it cannot fit.
            slots: Wished half-days (« mar. 22/09 après-midi »), kept before the summary and never cut.
            booked: The appointment booked in the agenda (« mar. 29/09 à 14:30 (Révision) »): the SMS opens on it.

        Returns:
            A one-segment GSM-7 text.
        """
        if booked:
            urgent = "URGENT, " if request_type is AiAssistantRequestType.URGENT else ""
            booked_heads = [
                f"{urgent}RDV réservé le {booked} par {cls._clip(name, max_chars)}, "
                f"{cls._clip(contact, cls._CONTACT_MAX_CHARS)}"
                for max_chars in (cls._NAME_MAX_CHARS, cls._SHORT_NAME_MAX_CHARS)
            ]
            fitting = [head for head in booked_heads if segment_count(to_strict_gsm7(head) + ".") <= 1]
            return cls._fit(fitting[0] if fitting else booked_heads[-1], summary, link)
        photos = " (photo)" if has_photos else ""
        heads = [
            f"{cls.LABELS[request_type]}{photos} de {cls._clip(name, max_chars)}, "
            f"{cls._clip(contact, cls._CONTACT_MAX_CHARS)}"
            for max_chars in (cls._NAME_MAX_CHARS, cls._SHORT_NAME_MAX_CHARS)
        ]
        return cls._fit(cls._with_slots(heads, slots), summary, link)

    @classmethod
    def reminder(
        cls,
        *,
        request_type: AiAssistantRequestType,
        name: str,
        contact: str,
        summary: str | None,
        received_local: datetime,
        link: str | None = None,
        slots: tuple[str, ...] = (),
    ) -> str:
        """
        The SMS reminding a request still waiting (« Rappel, en attente depuis le 23/09 : demande de devis… »).

        Args:
            request_type: Its type.
            name: The visitor's name.
            contact: Their phone or email.
            summary: What they need.
            received_local: When it came in, local time.
            link: The client space, without scheme; dropped when it cannot fit.
            slots: Wished half-days (« mar. 22/09 après-midi »), kept before the summary and never cut.

        Returns:
            A one-segment GSM-7 text.
        """
        heads = [
            f"Rappel, en attente depuis le {received_local:%d/%m} : {cls.REMINDER_LABELS[request_type]} de "
            f"{cls._clip(name, max_chars)}, {cls._clip(contact, cls._CONTACT_MAX_CHARS)}"
            for max_chars in (cls._NAME_MAX_CHARS, cls._SHORT_NAME_MAX_CHARS)
        ]
        return cls._fit(cls._with_slots(heads, slots), summary, link)

    @classmethod
    def _with_slots(cls, heads: list[str], slots: tuple[str, ...]) -> str:
        """
        The first head (full name, then a shorter one) that carries the wished half-days in one segment.

        Both half-days first, then only the first one; without them when even that overflows (the email has them).
        """
        for wished in (slots[:2], slots[:1]) if slots else ():
            for head in heads:
                candidate = f"{head}, pour {' ou '.join(wished)}"
                if segment_count(to_strict_gsm7(candidate) + ".") <= 1:
                    return candidate
        return heads[0]

    @classmethod
    def _clip(cls, text: str, max_chars: int) -> str:
        """A visitor-typed field, GSM-7 and bounded."""
        cleaned = to_strict_gsm7(text)
        return cleaned if len(cleaned) <= max_chars else cleaned[: max_chars - 3].rstrip() + "..."

    @classmethod
    def _fit(cls, head: str, summary: str | None, link: str | None = None) -> str:
        """
        ``head : summary. Suivi : link`` in one segment, the summary cut word by word; the link is added
        only while the summary keeps ``_MIN_SUMMARY_WITH_LINK`` characters (or all of a shorter one).
        """
        base = to_strict_gsm7(head)
        while segment_count(base + ".") > 1:  # only with extension characters (€, [ ]…) in every field
            base = base[:-1]
        words = to_strict_gsm7(summary or "").split()
        if link:
            text, kept = cls._fill(base, words, f" Suivi : {link}")
            if text is not None and kept >= min(cls._MIN_SUMMARY_WITH_LINK, len(" ".join(words))):
                return text
        text, _kept = cls._fill(base, words, "")
        return text or base + "."

    @staticmethod
    def _fill(base: str, words: list[str], tail: str) -> tuple[str | None, int]:
        """
        ``base : summary.tail``, the summary cut word by word until the text is one segment.

        Returns:
            The text and how many summary characters it kept, or (None, 0) when even ``base.tail`` overflows.
        """
        remaining = list(words)
        cut = False
        while remaining:
            ending = "..." if cut else ("" if remaining[-1].endswith((".", "!", "?")) else ".")
            kept = " ".join(remaining)
            text = f"{base} : {kept}{ending}{tail}"
            if segment_count(text) <= 1:
                return text, len(kept)
            remaining.pop()
            cut = True
        text = f"{base}.{tail}"
        return (text, 0) if segment_count(text) <= 1 else (None, 0)


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
        if assistant.status != AiAssistantStatus.DELIVERED.value:
            return
        settings = AlertSettings.of(assistant)
        current = now or _utc_now()
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
        current = now or _utc_now()
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
            if settings.wants_sms(AiAssistantRequestType(request.type)):
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
        from services.ai_assistant.request_service import ai_assistant_request_service

        current = now or _utc_now()
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
            if not self.claim(db, request, AiAssistantRequest.reminder_sent_at):
                continue
            reminded += 1
            request_type = AiAssistantRequestType(request.type)
            if settings.email_enabled:
                transcript = ai_assistant_request_service.transcript(db, request)
                await self._email_owner(db, request, assistant, transcript, is_reminder=True)
            if settings.wants_sms(request_type) and settings.phone_e164 is not None:
                text = AlertSms.reminder(
                    request_type=request_type,
                    name=request.name,
                    contact=request.contact,
                    summary=request.need_summary or request.need,
                    received_local=OpeningHoursCalendar.to_business_time(request.created_at),
                    link=AiAssistantClientLinks.sms_link(assistant.id),
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
        current = now or _utc_now()
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
        from services.ai_assistant.request_service import ai_assistant_request_service

        text = AlertSms.new_request(
            request_type=AiAssistantRequestType(request.type),
            name=request.name,
            contact=request.contact,
            summary=request.need_summary or request.need,
            has_photos=bool(ai_assistant_request_service.photo_urls(request)),
            link=AiAssistantClientLinks.sms_link(assistant.id),
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
        try:
            outcome = await sms_service.send_service_message(
                db,
                user_id=assistant.user_id,
                config=config,
                to_e164=phone_e164,
                text=text,
                recipient_name=f"{assistant.business_name} (alertes)",
            )
        except Exception:
            logger.warning("Alert SMS to assistant %s owner failed", assistant.id, exc_info=True)
            return False
        # A provider failure is already notified by the SMS service; a refusal before it is not.
        if not outcome.sent and outcome.message is None:
            AiAssistantRequestAlerts._log_sms_refusal(assistant, outcome.reason or "Refusé avant l'envoi.")
        return outcome.sent

    @staticmethod
    def _log_sms_refusal(assistant: AiAssistant, reason: str) -> None:
        """Record in the activity log why an owner alert SMS did not leave (it is not retried)."""
        logger.warning("Alert SMS to assistant %s owner not sent: %s", assistant.id, reason)
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_alert_sms_skipped",
            status=STATUS_WARNING,
            title=f"{assistant.business_name} · SMS d'alerte non envoyé",
            detail=reason,
            user_id=assistant.user_id,
            entity_type="prospect",
            entity_id=assistant.prospect_id,
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
        from services.ai_assistant.request_service import ai_assistant_request_service

        try:
            recipient = AiAssistantBusinessMailer.business_email(db, assistant)
            if not recipient:
                logger.info("Assistant %s: no business email for request %s", assistant.id, request.id)
                return
            rendered = AiAssistantRequestEmail.render(
                RequestEmailContent(
                    business_name=assistant.business_name,
                    assistant_name=assistant.assistant_name,
                    request_type=AiAssistantRequestType(request.type),
                    visitor_name=request.name,
                    contact=request.contact,
                    need=request.need,
                    need_summary=request.need_summary,
                    received_at=OpeningHoursCalendar.to_business_time(request.created_at),
                    received_outside_hours=request.received_outside_hours,
                    transcript=ai_assistant_request_analyzer.bound_transcript(transcript),
                    handled_url=AiAssistantRequestLinks.handled_url(request.id),
                    photo_urls=tuple(ai_assistant_request_service.photo_urls(request)),
                    is_reminder=is_reminder,
                    client_space_url=AiAssistantClientLinks.url(assistant.id),
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
        claimed = (
            db.query(AiAssistantRequest)
            .filter(
                AiAssistantRequest.id == request.id,
                AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
                column.is_(None),
            )
            .update({column: _utc_now()}, synchronize_session=False)
        )
        db.commit()
        db.refresh(request)
        return claimed == 1


ai_assistant_request_alerts = AiAssistantRequestAlerts()
