"""
The access to a client's Gmail: its row, a fresh access token, and a lost access.

The tokens are stored encrypted, like the agenda's, and kept valid by ``google_token_access``. A lost access puts the
mailbox in error: the client reconnects it from the client space.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from enums.ai_assistant_mailbox import AiAssistantMailboxStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_mailbox import AiAssistantMailbox
from services.activity_log_service import CATEGORY_ASSISTANT, STATUS_WARNING, activity_log_service
from services.ai_assistant.field_limits import SHORT_TEXT_MAX_CHARS
from services.ai_assistant.gmail_client import GmailError, gmail_client
from services.ai_assistant.google_token_access import GoogleTokenAccess
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.google_oauth_client import GoogleTokens

logger = logging.getLogger(__name__)


class AiAssistantMailboxAccess(GoogleTokenAccess):
    """Reaches a sold receptionist's Gmail with its stored tokens, and records a lost access."""

    @staticmethod
    def mailbox_of(db: Session, assistant: AiAssistant) -> AiAssistantMailbox | None:
        """The mailbox row of a receptionist, connected or in error."""
        return db.query(AiAssistantMailbox).filter(AiAssistantMailbox.assistant_id == assistant.id).first()

    @staticmethod
    def record_lost_access(db: Session, assistant: AiAssistant, mailbox: AiAssistantMailbox, exc: GmailError) -> None:
        """
        Put a mailbox whose access is lost in error, once, with the day and time it was lost.

        Args:
            db: Active database session (rolled back first).
            assistant: The receptionist.
            mailbox: The mailbox that failed.
            exc: What Google answered.
        """
        logger.warning("Mailbox of assistant %s lost its access: %s", assistant.id, exc)
        db.rollback()
        row = db.get(AiAssistantMailbox, mailbox.id)
        if row is None or row.status == AiAssistantMailboxStatus.ERROR.value:
            return
        moment = OpeningHoursCalendar.business_now()
        row.status = AiAssistantMailboxStatus.ERROR.value
        row.last_error = f"{moment:%d/%m à %H:%M} : l'accès à la boîte mail a été perdu, reconnectez-la"[
            :SHORT_TEXT_MAX_CHARS
        ]
        db.commit()
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action="assistant_mailbox_lost",
            status=STATUS_WARNING,
            title=f"{assistant.business_name} · la boîte Gmail n'est plus accessible",
            detail=f"{exc} : plus aucun brouillon n'est préparé. Le client doit reconnecter sa boîte depuis son espace.",
            user_id=assistant.user_id,
            entity_type="prospect",
            entity_id=assistant.prospect_id,
        )

    async def _refresh(self, refresh_token: str) -> GoogleTokens:
        """New tokens from the mailbox's Google client."""
        return await gmail_client.refresh(refresh_token)

    def _lost_access_error(self) -> GmailError:
        """The error of a mailbox whose refresh token is missing or unreadable."""
        return GmailError("Boîte mail sans accès durable", needs_reconnect=True)


ai_assistant_mailbox_access = AiAssistantMailboxAccess()
