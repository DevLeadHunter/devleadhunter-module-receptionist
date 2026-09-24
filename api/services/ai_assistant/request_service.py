"""
Structured requests captured by an assistant: one per widget session, typed and summarized.

A visitor who leaves their details through the widget becomes a request the business owner handles
(new → handled or dropped). The request links the session's conversation journal, knows whether it
came in outside the business hours, carries the photos sent during the session (a quote, urgent when a
photo shows an immediate risk), and is typed and summarized in the background (question, quote,
appointment, urgent) so the visitor is answered at once. It is announced once: a push to the
operator and, when the assistant is sold, the owner's alerts (``request_alerts.py``: summary email,
SMS); a demo never writes to the prospect. A visit flagged internal (the operator testing) is
recorded but never announced.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from core.database import SessionLocal
from enums.ai_assistant_photo import AiAssistantPhotoUrgency
from enums.ai_assistant_request import AiAssistantRequestChannel, AiAssistantRequestStatus, AiAssistantRequestType
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_message import AiAssistantMessage
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.photo_service import ai_assistant_photo_service
from services.ai_assistant.request_alerts import ai_assistant_request_alerts
from services.ai_assistant.request_analyzer import TranscriptLine, ai_assistant_request_analyzer
from services.ai_assistant.request_email import AiAssistantRequestEmail
from services.notification_service import notification_service

logger = logging.getLogger(__name__)

SESSION_ID_MAX_CHARS = 64
NAME_MAX_CHARS = 255
NEED_MAX_CHARS = 2000
OWNER_NOTE_MAX_CHARS = 2000
OWNER_LIST_LIMIT = 300
# A resubmission within the same visit updates its request; after this, or once the request was
# handled or dropped, the same browser leaves a new one (the widget keeps its session for good).
SESSION_MERGE_WINDOW = timedelta(hours=24)
# Requests the background follow-up should have announced by now: picked up again by the runner.
ANNOUNCEMENT_GRACE = timedelta(minutes=2)
ANNOUNCEMENT_RECOVERY_WINDOW = timedelta(days=1)


@dataclass(frozen=True)
class RequestCounts:
    """An assistant's requests over the last 7 and 30 days, and the share received outside its hours."""

    last_7_days: int = 0
    last_30_days: int = 0
    # Over the last 30 days, among the requests whose hours were known; None when none were.
    outside_hours_pct: int | None = None


class AiAssistantRequestService:
    """Captures requests from the widget and serves them to the owner."""

    def __init__(self) -> None:
        # Strong references: a fire-and-forget task nobody holds can be garbage-collected mid-run.
        self._background_tasks: set[asyncio.Task[None]] = set()

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
            now: Local time of the business (tests); defaults to now.

        Returns:
            ``(request, created)`` — ``created`` is False when an existing request was updated.
        """
        normalized_session = (session_id or "").strip()[:SESSION_ID_MAX_CHARS] or None
        conversation_id = self._conversation_id(db, assistant.id, normalized_session)
        clean_need = (need or "").strip()[:NEED_MAX_CHARS] or None
        clean_language = (language or "").strip()[:8] or None

        existing = self._open_request_for_session(db, assistant.id, normalized_session)
        if existing is not None:
            existing.name = name.strip()[:NAME_MAX_CHARS]
            existing.contact = contact.strip()[:NAME_MAX_CHARS]
            existing.need = clean_need or existing.need
            existing.language = clean_language or existing.language
            existing.conversation_id = conversation_id or existing.conversation_id
            ai_assistant_photo_service.attach_to_request(db, existing)
            db.commit()
            db.refresh(existing)
            return existing, False

        opening_hours = (assistant.knowledge_json or {}).get("opening_hours")
        request = AiAssistantRequest(
            user_id=assistant.user_id,
            prospect_id=assistant.prospect_id,
            assistant_id=assistant.id,
            conversation_id=conversation_id,
            session_id=normalized_session,
            type=AiAssistantRequestType.OTHER.value,
            status=AiAssistantRequestStatus.NEW.value,
            channel=channel.value,
            name=name.strip()[:NAME_MAX_CHARS],
            contact=contact.strip()[:NAME_MAX_CHARS],
            need=clean_need,
            language=clean_language,
            received_outside_hours=OpeningHoursCalendar.received_outside_hours(
                opening_hours if isinstance(opening_hours, list) else None,
                now or OpeningHoursCalendar.business_now(),
            ),
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
        request.type = self._type_with_photos(AiAssistantRequestType(request.type), request).value
        db.commit()
        db.refresh(request)
        return request

    def schedule_follow_up(self, request_id: int) -> None:
        """
        Type, summarize and announce a request in the background, without delaying the visitor.

        Args:
            request_id: The request just captured.
        """
        task = asyncio.create_task(self._follow_up_in_background(request_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def follow_up(self, db: Session, request: AiAssistantRequest, assistant: AiAssistant) -> None:
        """
        Type and summarize a request from its conversation, then announce it if not done yet.

        Args:
            db: Active database session (committed).
            request: The captured request.
            assistant: Its assistant.
        """
        transcript = self.transcript(db, request)
        analysis = await ai_assistant_request_analyzer.analyze(
            business_name=assistant.business_name, need=request.need, transcript=transcript
        )
        request_type = self._type_with_photos(analysis.type, request)
        request.type = request_type.value
        request.need_summary = analysis.summary or request.need
        db.commit()
        if request.is_test or not self._claim_announcement(db, request):
            return
        await notification_service.notify_assistant_lead(
            db,
            user_id=assistant.user_id,
            prospect_id=assistant.prospect_id,
            fallback_name=assistant.business_name,
            lead_name=request.name,
            need=request.need_summary or request.need or "",
            request_label=AiAssistantRequestEmail.type_label(request_type),
            received_outside_hours=request.received_outside_hours,
        )
        await ai_assistant_request_alerts.alert_owner(db, request, assistant, transcript)

    def transcript(self, db: Session, request: AiAssistantRequest) -> list[TranscriptLine]:
        """
        The conversation of the request's widget session, oldest first.

        Args:
            db: Active database session.
            request: The request.

        Returns:
            The journaled turns (empty when the visitor wrote nothing before leaving details).
        """
        if request.conversation_id is None:
            return []
        messages = (
            db.query(AiAssistantMessage)
            .filter(AiAssistantMessage.conversation_id == request.conversation_id)
            .order_by(AiAssistantMessage.id)
            .all()
        )
        return [TranscriptLine(role=message.role, content=message.content) for message in messages]

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
            request.owner_note = owner_note.strip()[:OWNER_NOTE_MAX_CHARS] or None
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

    def unannounced_request_ids(self, db: Session, *, now: datetime | None = None) -> list[int]:
        """
        Real requests whose announcement was lost (restart mid follow-up, crash), to pick up again.

        Args:
            db: Active database session.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            Ids of requests still new, captured between one day and two minutes ago, never announced.
        """
        current = now or datetime.now(UTC).replace(tzinfo=None)
        rows = (
            db.query(AiAssistantRequest.id)
            .filter(
                AiAssistantRequest.owner_notified_at.is_(None),
                AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
                AiAssistantRequest.is_test.is_(False),
                AiAssistantRequest.legacy_lead_id.is_(None),
                AiAssistantRequest.created_at <= current - ANNOUNCEMENT_GRACE,
                AiAssistantRequest.created_at >= current - ANNOUNCEMENT_RECOVERY_WINDOW,
            )
            .order_by(AiAssistantRequest.id)
            .all()
        )
        return [row[0] for row in rows]

    async def announce_pending(self) -> int:
        """
        Run the follow-up of every request whose announcement was lost (called by the runner).

        Returns:
            How many requests were picked up.
        """
        db = SessionLocal()
        try:
            request_ids = self.unannounced_request_ids(db)
        finally:
            db.close()
        for request_id in request_ids:
            await self._follow_up_in_background(request_id)
        return len(request_ids)

    @staticmethod
    def photo_urls(request: AiAssistantRequest) -> list[str]:
        """
        Public URLs of the photos attached to a request.

        Args:
            request: The request.

        Returns:
            The photo URLs, in upload order (empty when none).
        """
        return [
            str(photo["url"])
            for photo in (request.photos_json or [])
            if isinstance(photo, dict) and isinstance(photo.get("url"), str)
        ]

    @staticmethod
    def _type_with_photos(analyzed: AiAssistantRequestType, request: AiAssistantRequest) -> AiAssistantRequestType:
        """A request with photos asks for a quote — urgent when a photo shows an immediate risk."""
        photos = [entry for entry in (request.photos_json or []) if isinstance(entry, dict)]
        if not photos:
            return analyzed
        if any(entry.get("urgency") == AiAssistantPhotoUrgency.HIGH.value for entry in photos):
            return AiAssistantRequestType.URGENT
        if analyzed in (
            AiAssistantRequestType.QUOTE,
            AiAssistantRequestType.APPOINTMENT,
            AiAssistantRequestType.URGENT,
        ):
            return analyzed
        return AiAssistantRequestType.QUOTE

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
    def _claim_announcement(db: Session, request: AiAssistantRequest) -> bool:
        """Atomically take the right to announce a request, so concurrent follow-ups announce it once."""
        return ai_assistant_request_alerts.claim(db, request, AiAssistantRequest.owner_notified_at)

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

    async def _follow_up_in_background(self, request_id: int) -> None:
        """Run :meth:`follow_up` on a fresh session; never raises."""
        db = SessionLocal()
        try:
            request = db.get(AiAssistantRequest, request_id)
            assistant = db.get(AiAssistant, request.assistant_id) if request else None
            if request is None or assistant is None:
                return
            await self.follow_up(db, request, assistant)
        except Exception:
            logger.exception("Assistant request %s follow-up failed", request_id)
            db.rollback()
        finally:
            db.close()


ai_assistant_request_service = AiAssistantRequestService()
