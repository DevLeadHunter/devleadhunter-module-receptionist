"""
The weekly email of the questions a sold assistant could not answer.

Every Monday morning (business time), a business whose assistant met questions its knowledge could not answer during
the past week gets them by email, with the link to its space where one answer turns each of them into a reply for
the next visitor. One email per assistant and per week at most, remembered in the knowledge; a week without new
unanswered question sends nothing. A demo, a muted business or an assistant without an address is never emailed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from core.database import SessionLocal
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from services.ai_assistant.business_mailer import AiAssistantBusinessMailer
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.client_space_email import AiAssistantClientSpaceEmail
from services.ai_assistant.faq_service import UnansweredQuestion, ai_assistant_faq_service
from services.ai_assistant.opening_hours import OpeningHoursCalendar

logger = logging.getLogger(__name__)

DIGEST_WEEKDAY = 0  # Monday
DIGEST_HOUR = 8  # business local time
DIGEST_WINDOW = timedelta(days=7)


def _utc_now() -> datetime:
    """Current time as naive UTC, the storage convention."""
    return datetime.now(UTC).replace(tzinfo=None)


class AiAssistantUnansweredDigest:
    """Sends, once a week, the questions each sold assistant could not answer to its business."""

    @staticmethod
    def week_key(local: datetime) -> str:
        """
        The ISO week a local moment belongs to, as stored on the assistant once its digest went.

        Args:
            local: A moment in the business's local time.

        Returns:
            « 2026-W40 ».
        """
        year, week, _weekday = local.isocalendar()
        return f"{year}-W{week:02d}"

    @staticmethod
    def is_due_moment(local: datetime) -> bool:
        """
        Whether a local moment is in the sending window: Monday, from 8 h.

        Args:
            local: A moment in the business's local time.

        Returns:
            True on a Monday at or after the digest hour.
        """
        return local.weekday() == DIGEST_WEEKDAY and local.hour >= DIGEST_HOUR

    @staticmethod
    def recent_questions(assistant: AiAssistant, *, now: datetime) -> list[UnansweredQuestion]:
        """
        The unanswered questions asked during the past week, most asked first.

        Args:
            assistant: The assistant.
            now: Current naive UTC time.

        Returns:
            The questions whose last occurrence is less than a week old.
        """
        since = now - DIGEST_WINDOW
        recent = [
            entry
            for entry in ai_assistant_faq_service.unanswered_of(assistant.knowledge_json)
            if entry.last_seen is not None and entry.last_seen >= since
        ]
        return sorted(recent, key=lambda entry: (-entry.count, entry.last_seen or datetime.min))

    async def run_pass(self) -> None:
        """Send the digests due, in a session of its own; a failure is logged and never stops the runner."""
        try:
            with SessionLocal() as db:
                sent = await self.send_due(db)
            if sent:
                logger.info("Unanswered-question digests sent: %s", sent)
        except Exception:
            logger.exception("Unanswered-question digest pass failed")

    async def send_due(self, db: Session, *, now: datetime | None = None) -> int:
        """
        Send this week's digest to every sold assistant that has not had it yet.

        Args:
            db: Active database session.
            now: Current naive UTC time (tests); defaults to now.

        Returns:
            How many emails went.
        """
        current = now or _utc_now()
        local = OpeningHoursCalendar.to_business_time(current)
        if not self.is_due_moment(local):
            return 0
        week = self.week_key(local)
        assistants = (
            db.query(AiAssistant)
            .filter(AiAssistant.status == AiAssistantStatus.DELIVERED.value, AiAssistant.deleted_at.is_(None))
            .order_by(AiAssistant.id)
            .all()
        )
        sent = 0
        for assistant in assistants:
            if ai_assistant_faq_service.unanswered_digest_week(assistant) == week:
                continue
            # Marked first: a business is examined once a week, whatever the sending does.
            ai_assistant_faq_service.mark_unanswered_digest(db, assistant, week)
            questions = self.recent_questions(assistant, now=current)
            if not questions or AiAssistantBusinessMailer.is_muted(db, assistant):
                continue
            recipient = AiAssistantBusinessMailer.business_email(db, assistant)
            if not recipient:
                continue
            rendered = AiAssistantClientSpaceEmail.render_unanswered_digest(
                business_name=assistant.business_name,
                assistant_name=assistant.assistant_name,
                questions=questions,
                url=AiAssistantClientLinks.url(assistant, now=current),
            )
            failure = await AiAssistantBusinessMailer.send(
                db, assistant, rendered, recipient=recipient, recipient_name=assistant.business_name
            )
            if failure is None:
                sent += 1
            else:
                logger.warning("Unanswered digest of assistant %s not sent: %s", assistant.id, failure)
        return sent


ai_assistant_unanswered_digest = AiAssistantUnansweredDigest()
