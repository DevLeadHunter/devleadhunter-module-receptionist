"""
Structured requests captured by an assistant: one per widget session, served to the owner.

A visitor who leaves their details through the widget becomes a request the business owner handles
(new → handled or dropped). The request links the session's conversation journal, knows whether it
came in outside the business hours and carries the photos sent during the session (a quote, urgent when
a photo shows an immediate risk: ``request_attachments``). It is typed, summarized and announced once in
the background (``request_follow_up``), so the visitor is answered at once; a visit flagged internal
(the operator testing) is recorded but never announced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from enums.ai_assistant_request import (
    AiAssistantRequestChannel,
    AiAssistantRequestOutcome,
    AiAssistantRequestStatus,
    AiAssistantRequestType,
)
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.alert_settings import AlertSettings, QuietHours
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots, AppointmentSlot
from services.ai_assistant.field_limits import LONG_TEXT_MAX_CHARS, SESSION_ID_MAX_CHARS, SHORT_TEXT_MAX_CHARS
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.photo_service import ai_assistant_photo_service
from services.ai_assistant.request_attachments import AiAssistantRequestAttachments

OWNER_LIST_LIMIT = 300
# A resubmission within the same visit updates its request; after this, or once the request was
# handled or dropped, the same browser leaves a new one (the widget keeps its session for good).
SESSION_MERGE_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class RequestCounts:
    """An assistant's requests over the last 7 and 30 days, and the share received outside its hours."""

    last_7_days: int = 0
    last_30_days: int = 0
    # Over the last 30 days, among the requests whose hours were known; None when none were.
    outside_hours_pct: int | None = None


class AiAssistantRequestService:
    """Captures requests from the widget and serves them to the owner."""

    def capture(
        self,
        db: Session,
        *,
        assistant: AiAssistant,
        name: str,
        contact: str,
        need: str | None,
        language: str | None,
        session_id: str | None,
        is_test: bool = False,
        channel: AiAssistantRequestChannel = AiAssistantRequestChannel.SITE,
        appointment_slots: list[AppointmentSlot] | None = None,
        now: datetime | None = None,
    ) -> tuple[AiAssistantRequest, bool]:
        """
        Create the session's request, or update the one the visitor already left.

        Args:
            db: Active database session (committed).
            assistant: The assistant the visitor talked to.
            name: The visitor's name.
            contact: Their phone or email, as typed.
            need: What they typed in the form, if anything.
            language: The widget language.
            session_id: The widget session — one request per session.
            is_test: The operator testing (``?internal=1``): recorded, never announced.
            channel: Where the request came in.
            appointment_slots: The half-days the visitor wishes an appointment in (at most two, still offered).
            now: Local time of the business (tests); defaults to now.

        Returns:
            ``(request, created)`` — ``created`` is False when an existing request was updated.

        Raises:
            ValueError: When a wished half-day is not offered (nothing is saved).
        """
        hours = AiAssistantAppointmentSlots.opening_hours_of(assistant)
        local_now = now or OpeningHoursCalendar.business_now()
        slots_json = (
            AiAssistantAppointmentSlots.to_json(
                AiAssistantAppointmentSlots.check(hours, appointment_slots, today=local_now.date())
            )
            if appointment_slots
            else None
        )
        normalized_session = (session_id or "").strip()[:SESSION_ID_MAX_CHARS] or None
        conversation_id = self._conversation_id(db, assistant.id, normalized_session)
        clean_need = (need or "").strip()[:LONG_TEXT_MAX_CHARS] or None
        clean_language = (language or "").strip()[:8] or None

        existing = self._open_request_for_session(db, assistant.id, normalized_session)
        if existing is not None:
            existing.name = name.strip()[:SHORT_TEXT_MAX_CHARS]
            existing.contact = contact.strip()[:SHORT_TEXT_MAX_CHARS]
            existing.need = clean_need or existing.need
            existing.language = clean_language or existing.language
            existing.conversation_id = conversation_id or existing.conversation_id
            if slots_json:
                existing.appointment_slots_json = slots_json
                if existing.type != AiAssistantRequestType.URGENT.value:
                    existing.type = AiAssistantRequestType.APPOINTMENT.value
            ai_assistant_photo_service.attach_to_request(db, existing)
            db.commit()
            db.refresh(existing)
            return existing, False

        request = AiAssistantRequest(
            user_id=assistant.user_id,
            prospect_id=assistant.prospect_id,
            assistant_id=assistant.id,
            conversation_id=conversation_id,
            session_id=normalized_session,
            # Half-days picked in the widget: an appointment request from the start (an urgency read later wins).
            type=(AiAssistantRequestType.APPOINTMENT if slots_json else AiAssistantRequestType.OTHER).value,
            status=AiAssistantRequestStatus.NEW.value,
            channel=channel.value,
            name=name.strip()[:SHORT_TEXT_MAX_CHARS],
            contact=contact.strip()[:SHORT_TEXT_MAX_CHARS],
            need=clean_need,
            language=clean_language,
            received_outside_hours=OpeningHoursCalendar.received_outside_hours(hours, local_now),
            appointment_slots_json=slots_json,
            is_test=is_test,
        )
        db.add(request)
        db.flush()
        ai_assistant_photo_service.attach_to_request(db, request)
        db.commit()
        db.refresh(request)
        return request, True

    def attach_late_photos(self, db: Session, *, assistant_id: int, session_id: str) -> AiAssistantRequest | None:
        """
        Add a photo sent after the contact details to the request this visit already left.

        The request becomes a quote (or urgent) if it was not; the owner, already alerted, sees the photo
        in the dashboard and in the reminder.

        Args:
            db: Active database session (committed).
            assistant_id: The assistant.
            session_id: The widget session.

        Returns:
            The updated request, or None when the visit has left none still open.
        """
        request = self._open_request_for_session(db, assistant_id, session_id.strip()[:SESSION_ID_MAX_CHARS])
        if request is None:
            return None
        ai_assistant_photo_service.attach_to_request(db, request)
        previous_type = AiAssistantRequestType(request.type)
        request.type = AiAssistantRequestAttachments.type_with_photos(previous_type, request).value
        if request.type == AiAssistantRequestType.URGENT.value and previous_type is not AiAssistantRequestType.URGENT:
            self._plan_sms_for_late_urgency(db, request)
        db.commit()
        db.refresh(request)
        return request

    @staticmethod
    def _plan_sms_for_late_urgency(db: Session, request: AiAssistantRequest) -> None:
        """A request already announced that a photo just made urgent gets the owner's SMS now, or after the quiet
        window; nothing changes when it was not announced yet (the follow-up will text it) or was texted already."""
        if request.owner_alerted_at is None or request.sms_sent_at is not None or request.sms_due_at is not None:
            return
        assistant = db.get(AiAssistant, request.assistant_id)
        if assistant is None:
            return
        settings = AlertSettings.of(assistant)
        if not settings.wants_sms(AiAssistantRequestType.URGENT):
            return
        now_utc = datetime.now(UTC).replace(tzinfo=None)
        local = OpeningHoursCalendar.to_business_time(now_utc)
        release = QuietHours.release_at(local, settings.quiet_start_hour, settings.quiet_end_hour)
        request.sms_due_at = now_utc if release == local else OpeningHoursCalendar.to_utc(release)

    def list_for_owner(
        self,
        db: Session,
        user_id: int,
        *,
        assistant_id: int | None = None,
        status: AiAssistantRequestStatus | None = None,
    ) -> list[tuple[AiAssistantRequest, str]]:
        """
        The owner's requests with their business name, newest first.

        Args:
            db: Active database session.
            user_id: The owner.
            assistant_id: Only this assistant's requests, when set.
            status: Only requests in this status, when set.

        Returns:
            ``(request, business_name)`` pairs, at most ``OWNER_LIST_LIMIT``.
        """
        query = (
            db.query(AiAssistantRequest, AiAssistant.business_name)
            .join(AiAssistant, AiAssistant.id == AiAssistantRequest.assistant_id)
            .filter(AiAssistantRequest.user_id == user_id, AiAssistant.deleted_at.is_(None))
        )
        if assistant_id is not None:
            query = query.filter(AiAssistantRequest.assistant_id == assistant_id)
        if status is not None:
            query = query.filter(AiAssistantRequest.status == status.value)
        return query.order_by(AiAssistantRequest.created_at.desc()).limit(OWNER_LIST_LIMIT).all()

    def get_for_owner(self, db: Session, user_id: int, request_id: int) -> AiAssistantRequest | None:
        """
        One of the owner's requests.

        Args:
            db: Active database session.
            user_id: The owner.
            request_id: The request.

        Returns:
            The request, or None when it does not exist or belongs to someone else.
        """
        return (
            db.query(AiAssistantRequest)
            .filter(AiAssistantRequest.id == request_id, AiAssistantRequest.user_id == user_id)
            .first()
        )

    def update_for_owner(
        self,
        db: Session,
        request: AiAssistantRequest,
        *,
        status: AiAssistantRequestStatus | None = None,
        owner_note: str | None = None,
    ) -> AiAssistantRequest:
        """
        Change a request's status and/or note (only the fields given).

        Args:
            db: Active database session (committed).
            request: The owner's request.
            status: New status, when changing it.
            owner_note: New note, when changing it (empty clears it).

        Returns:
            The updated request.
        """
        if status is not None:
            self._set_status(request, status)
        if owner_note is not None:
            request.owner_note = owner_note.strip()[:LONG_TEXT_MAX_CHARS] or None
        db.commit()
        db.refresh(request)
        return request

    def mark_handled(self, db: Session, request: AiAssistantRequest) -> bool:
        """
        Mark a request handled (from the signed email link).

        Args:
            db: Active database session (committed).
            request: The request.

        Returns:
            True when it changed, False when it was already handled or dropped.
        """
        if request.status != AiAssistantRequestStatus.NEW.value:
            return False
        self._set_status(request, AiAssistantRequestStatus.HANDLED)
        db.commit()
        return True

    def mark_dropped(self, db: Session, request: AiAssistantRequest) -> bool:
        """
        Set a request aside (a test, spam, a duplicate): out of the things to do, not handled either.

        Args:
            db: Active database session (committed).
            request: The request.

        Returns:
            True when it changed, False when it was already handled or dropped.
        """
        if request.status != AiAssistantRequestStatus.NEW.value:
            return False
        self._set_status(request, AiAssistantRequestStatus.DROPPED)
        db.commit()
        return True

    def set_outcome(self, db: Session, request: AiAssistantRequest, outcome: AiAssistantRequestOutcome | None) -> bool:
        """
        Note what became of a request the owner called back: a client won, lost, or nothing yet.

        Args:
            db: Active database session (committed).
            request: The request.
            outcome: The outcome, or None to clear it.

        Returns:
            True when it changed; False for a request set aside, which has no outcome.
        """
        if request.status == AiAssistantRequestStatus.DROPPED.value:
            return False
        if request.status == AiAssistantRequestStatus.NEW.value and outcome is not None:
            self._set_status(request, AiAssistantRequestStatus.HANDLED)
        request.outcome = outcome.value if outcome is not None else None
        request.outcome_at = datetime.now(UTC).replace(tzinfo=None) if outcome is not None else None
        db.commit()
        return True

    def counts_for_assistants(self, db: Session, assistant_ids: list[int]) -> dict[int, RequestCounts]:
        """
        Request counts per assistant for the dashboard list (tests excluded), in one aggregate query.

        Args:
            db: Active database session.
            assistant_ids: The assistants listed.

        Returns:
            Counts keyed by assistant id (every id present).
        """
        if not assistant_ids:
            return {}
        now = datetime.now(UTC).replace(tzinfo=None)
        rows = (
            db.query(
                AiAssistantRequest.assistant_id,
                func.count(AiAssistantRequest.id),
                func.sum(case((AiAssistantRequest.created_at >= now - timedelta(days=7), 1), else_=0)),
                func.sum(case((AiAssistantRequest.received_outside_hours.is_(True), 1), else_=0)),
                func.sum(case((AiAssistantRequest.received_outside_hours.is_not(None), 1), else_=0)),
            )
            .filter(
                AiAssistantRequest.assistant_id.in_(assistant_ids),
                AiAssistantRequest.is_test.is_(False),
                AiAssistantRequest.created_at >= now - timedelta(days=30),
            )
            .group_by(AiAssistantRequest.assistant_id)
            .all()
        )
        counts: dict[int, RequestCounts] = {assistant_id: RequestCounts() for assistant_id in assistant_ids}
        for assistant_id, last_30_days, last_7_days, outside_hours, known_hours in rows:
            counts[assistant_id] = RequestCounts(
                last_7_days=int(last_7_days or 0),
                last_30_days=int(last_30_days or 0),
                outside_hours_pct=round(100 * int(outside_hours or 0) / int(known_hours)) if known_hours else None,
            )
        return counts

    def pending_count(self, db: Session, user_id: int) -> int:
        """
        How many of the owner's real requests still wait for handling.

        Args:
            db: Active database session.
            user_id: The owner.

        Returns:
            The number of ``new`` requests (tests excluded).
        """
        return (
            db.query(func.count(AiAssistantRequest.id))
            .join(AiAssistant, AiAssistant.id == AiAssistantRequest.assistant_id)
            .filter(
                AiAssistantRequest.user_id == user_id,
                AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
                AiAssistantRequest.is_test.is_(False),
                AiAssistant.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )

    @staticmethod
    def _set_status(request: AiAssistantRequest, status: AiAssistantRequestStatus) -> None:
        """Apply a status and keep ``handled_at`` in step with it."""
        request.status = status.value
        request.handled_at = (
            datetime.now(UTC).replace(tzinfo=None) if status is not AiAssistantRequestStatus.NEW else None
        )

    @staticmethod
    def _open_request_for_session(db: Session, assistant_id: int, session_id: str | None) -> AiAssistantRequest | None:
        """The session's request still waiting for handling and recent enough to be the same visit."""
        if not session_id:
            return None
        return (
            db.query(AiAssistantRequest)
            .filter(
                AiAssistantRequest.assistant_id == assistant_id,
                AiAssistantRequest.session_id == session_id,
                AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
                AiAssistantRequest.created_at >= datetime.now(UTC).replace(tzinfo=None) - SESSION_MERGE_WINDOW,
            )
            .order_by(AiAssistantRequest.id.desc())
            .first()
        )

    @staticmethod
    def _conversation_id(db: Session, assistant_id: int, session_id: str | None) -> int | None:
        """The journaled conversation of this widget session, if the visitor chatted first."""
        if not session_id:
            return None
        return (
            db.query(AiAssistantConversation.id)
            .filter(
                AiAssistantConversation.assistant_id == assistant_id,
                AiAssistantConversation.session_id == session_id,
            )
            .order_by(AiAssistantConversation.id.desc())
            .limit(1)
            .scalar()
        )


ai_assistant_request_service = AiAssistantRequestService()
