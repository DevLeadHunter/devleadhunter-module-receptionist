"""
The follow-up of a captured request: typed and summarized in the background, then announced once.

The visitor is answered at once; the model then reads the conversation (question, quote, appointment, urgent)
and writes the summary. The request is announced once: a push to the operator and, when the assistant is sold,
the owner's alerts (``request_alerts``: summary email, SMS); a demo never writes to the prospect. A visit flagged
internal (the operator testing) is typed but never announced. An announcement lost to a restart is picked up
again by the runner.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from core.clock import naive_utc_now
from core.database import SessionLocal
from enums.ai_assistant_request import AiAssistantRequestStatus, AiAssistantRequestType
from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.request_alerts import ai_assistant_request_alerts
from services.ai_assistant.request_analyzer import RequestAnalysis, ai_assistant_request_analyzer
from services.ai_assistant.request_attachments import AiAssistantRequestAttachments
from services.ai_assistant.request_email import AiAssistantRequestEmail
from services.notification_service import notification_service

logger = logging.getLogger(__name__)

# Requests the background follow-up should have announced by now: picked up again by the runner.
ANNOUNCEMENT_GRACE = timedelta(minutes=2)
ANNOUNCEMENT_RECOVERY_WINDOW = timedelta(days=1)


class AiAssistantRequestFollowUp:
    """Types, summarizes and announces the captured requests, and picks up the announcements a restart lost."""

    def __init__(self) -> None:
        # Strong references: a fire-and-forget task nobody holds can be garbage-collected mid-run.
        self._background_tasks: set[asyncio.Task[None]] = set()

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
        transcript = AiAssistantRequestAttachments.transcript(db, request)
        business_name = assistant.business_name
        need = request.need
        eu_only = bool(assistant.eu_only)
        # The model may take 20 s: the pool connection goes back meanwhile.
        db.commit()
        analysis = await ai_assistant_request_analyzer.analyze(
            business_name=business_name,
            need=need,
            transcript=transcript,
            eu_only=eu_only,
        )
        # A photo attached meanwhile may have made the request urgent: that reading wins over the words.
        db.refresh(request)
        if request.type == AiAssistantRequestType.URGENT.value:
            analysis = RequestAnalysis(
                type=AiAssistantRequestType.URGENT, summary=analysis.summary, event=analysis.event
            )
        # Half-days or a slot picked in the widget make it an appointment request, unless the words say it is urgent.
        booked = (
            db.query(AiAssistantAppointment.id)
            .filter(
                AiAssistantAppointment.request_id == request.id,
                AiAssistantAppointment.google_event_id.is_not(None),
            )
            .first()
        )
        analyzed = (
            AiAssistantRequestType.APPOINTMENT
            if (request.appointment_slots_json or booked is not None) and analysis.type != AiAssistantRequestType.URGENT
            else analysis.type
        )
        request_type = AiAssistantRequestAttachments.type_with_photos(analyzed, request)
        request.type = request_type.value
        request.need_summary = analysis.summary or request.need
        request.event_json = asdict(analysis.event) if analysis.event is not None else None
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

    def unannounced_request_ids(self, db: Session, *, now: datetime | None = None) -> list[int]:
        """
        Real requests whose announcement was lost (restart mid follow-up, crash), to pick up again.

        Args:
            db: Active database session.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            Ids of requests still new, captured between one day and two minutes ago, never announced.
        """
        current = now or naive_utc_now()
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
    def _claim_announcement(db: Session, request: AiAssistantRequest) -> bool:
        """Atomically take the right to announce a request, so concurrent follow-ups announce it once."""
        return ai_assistant_request_alerts.claim(db, request, AiAssistantRequest.owner_notified_at)

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


ai_assistant_request_follow_up = AiAssistantRequestFollowUp()
