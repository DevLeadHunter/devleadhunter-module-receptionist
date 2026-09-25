"""
Emails to a sold assistant's business, sent from the operator's own identity as transactional mail.

The business's address is the assistant's own, else its prospect's, else the one the paying client gave at the
Stripe checkout of its running subscription.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from enums.assistant_subscription_status import LIVE_SUBSCRIPTION_STATUSES
from models.ai_assistant import AiAssistant
from models.ai_assistant_subscription import AiAssistantSubscription
from models.prospect_db import ProspectDB
from services.ai_assistant.request_email import RenderedEmail
from services.email_sending_service import EmailSendingService

logger = logging.getLogger(__name__)


class AiAssistantBusinessMailer:
    """Finds the business's address and emails it from the operator's identity."""

    @staticmethod
    def is_muted(db: Session, assistant: AiAssistant) -> bool:
        """
        Whether the business asked never to be contacted: no email, SMS or report may reach it.

        Args:
            db: Active database session.
            assistant: The assistant.

        Returns:
            True when its prospect carries the « ne plus contacter » flag.
        """
        if assistant.prospect_id is None:
            return False
        flagged = db.query(ProspectDB.do_not_contact).filter(ProspectDB.id == assistant.prospect_id).scalar()
        return bool(flagged)

    @classmethod
    def business_email(cls, db: Session, assistant: AiAssistant) -> str | None:
        """
        The business's contact address.

        Args:
            db: Active database session.
            assistant: The assistant.

        Returns:
            The assistant's address, else its prospect's, else the paying client's; None when there is none or
            when the business asked never to be contacted.
        """
        if cls.is_muted(db, assistant):
            logger.info("Assistant %s: its business is flagged « ne plus contacter », no email leaves", assistant.id)
            return None
        if assistant.email and assistant.email.strip():
            return assistant.email.strip()
        if assistant.prospect_id is not None:
            email = db.query(ProspectDB.email).filter(ProspectDB.id == assistant.prospect_id).scalar()
            if email and email.strip():
                return email.strip()
        client_email = (
            db.query(AiAssistantSubscription.client_email)
            .filter(
                AiAssistantSubscription.ai_assistant_id == assistant.id,
                AiAssistantSubscription.status.in_(LIVE_SUBSCRIPTION_STATUSES),
                AiAssistantSubscription.client_email.is_not(None),
            )
            .order_by(AiAssistantSubscription.created_at.desc())
            .limit(1)
            .scalar()
        )
        return client_email.strip() if client_email and client_email.strip() else None

    @staticmethod
    async def send(
        db: Session,
        assistant: AiAssistant,
        rendered: RenderedEmail,
        *,
        recipient: str,
        recipient_name: str | None,
        bcc: list[str] | None = None,
    ) -> str | None:
        """
        Send an email from the operator's identity, transactional (the prospect is not marked contacted).

        Args:
            db: Active database session (rolled back when the sending fails).
            assistant: The assistant the email is about.
            rendered: Its subject and body.
            recipient: Where it goes.
            recipient_name: The name shown for the recipient.
            bcc: Blind copies, when any.

        Returns:
            None when the email left, else why it did not; it never raises.
        """
        try:
            send_outcome = await EmailSendingService(db).send_via_user_identity(
                user_id=assistant.user_id,
                recipient_email=recipient,
                recipient_name=recipient_name,
                subject=rendered.subject,
                body_html=rendered.html,
                bcc=bcc,
                is_transactional=True,
            )
        except Exception as exc:
            logger.warning("Email of assistant %s could not be sent", assistant.id, exc_info=True)
            db.rollback()
            return str(exc) or type(exc).__name__
        if not send_outcome.get("success"):
            return str(send_outcome.get("error") or "Échec de l'envoi.")
        return None
