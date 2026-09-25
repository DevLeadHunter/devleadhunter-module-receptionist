"""Server-side journal of the conversations visitors have with an assistant.

Once sold, the widget runs on the client's site where our analytics cannot see it: this journal is
the owner's only window on what visitors ask (« ce que vos visiteurs ont demandé »), the proof of
value shown to the client, and the churn signal when it goes quiet.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_message import AiAssistantMessage

# A stored turn is bounded like the chat input (services.ai_assistant.chat_service.MAX_MESSAGE_CHARS).
MAX_STORED_MESSAGE_CHARS = 2000
SESSION_ID_MAX_CHARS = 64
RETENTION_DAYS = 90
RECENT_CONVERSATIONS_LIMIT = 20


@dataclass(frozen=True)
class ConversationCounts:
    """How many conversations an assistant had over the last 7 and 30 days (tests excluded)."""

    last_7_days: int = 0
    last_30_days: int = 0


class AiAssistantConversationService:
    """Records each chat turn and serves the owner's read-only journal."""

    def record_turn(
        self,
        db: Session,
        *,
        assistant: AiAssistant,
        session_id: str | None,
        language: str | None,
        visitor_message: str,
        reply: str,
        is_test: bool = False,
        visitor_photo_url: str | None = None,
    ) -> AiAssistantConversation:
        """Append a visitor message and the assistant's reply to the session's conversation.

        Args:
            db: Active database session.
            assistant: The assistant that answered.
            session_id: The widget's session id; a random one is used when the widget sent none.
            language: The widget language at that moment, when known.
            visitor_message: What the visitor wrote.
            reply: What the assistant answered.
            is_test: Sent from an internal visit (``?internal=1``): the conversation stays out of the counts.
            visitor_photo_url: The photo the visitor's turn carried, when it was one.

        Returns:
            The conversation the turn was appended to.
        """
        conversation = self._conversation_for_session(db, assistant=assistant, session_id=session_id, language=language)
        if is_test:
            conversation.is_test = True
        now: datetime = datetime.now(UTC).replace(tzinfo=None)
        for role, content, photo_url in (("user", visitor_message, visitor_photo_url), ("assistant", reply, None)):
            conversation.messages.append(
                AiAssistantMessage(
                    role=role, content=content.strip()[:MAX_STORED_MESSAGE_CHARS], photo_url=photo_url, created_at=now
                )
            )
        conversation.message_count += 2
        conversation.last_message_at = now
        db.commit()
        db.refresh(conversation)
        return conversation

    def counts_for_assistants(self, db: Session, assistant_ids: list[int]) -> dict[int, ConversationCounts]:
        """
        Conversations active over the last 7 and 30 days, keyed by assistant id (for the dashboard list).

        A returning visitor goes on in the conversation of their session: it counts when its last message
        falls in the window, however old its start. Tests are left out.

        Args:
            db: Active database session.
            assistant_ids: The assistants listed.

        Returns:
            Counts keyed by assistant id (every id present).
        """
        if not assistant_ids:
            return {}
        now: datetime = datetime.now(UTC).replace(tzinfo=None)
        last_7_days = self._counts_since(db, assistant_ids, now - timedelta(days=7))
        last_30_days = self._counts_since(db, assistant_ids, now - timedelta(days=30))
        return {
            assistant_id: ConversationCounts(
                last_7_days=last_7_days.get(assistant_id, 0), last_30_days=last_30_days.get(assistant_id, 0)
            )
            for assistant_id in assistant_ids
        }

    def recent_for_assistant(self, db: Session, assistant_id: int) -> list[AiAssistantConversation]:
        """The assistant's latest conversations with their messages, newest first."""
        return (
            db.query(AiAssistantConversation)
            .options(selectinload(AiAssistantConversation.messages))
            .filter(AiAssistantConversation.assistant_id == assistant_id)
            .order_by(AiAssistantConversation.last_message_at.desc())
            .limit(RECENT_CONVERSATIONS_LIMIT)
            .all()
        )

    def purge_old(self, db: Session) -> int:
        """Delete the conversations quiet for longer than the retention window, messages included.

        Returns:
            The number of conversations deleted.
        """
        cutoff: datetime = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=RETENTION_DAYS)
        stale: list[AiAssistantConversation] = (
            db.query(AiAssistantConversation).filter(AiAssistantConversation.last_message_at < cutoff).all()
        )
        for conversation in stale:
            db.delete(conversation)
        if stale:
            db.commit()
        return len(stale)

    def _conversation_for_session(
        self, db: Session, *, assistant: AiAssistant, session_id: str | None, language: str | None
    ) -> AiAssistantConversation:
        normalized_session: str = (session_id or "").strip()[:SESSION_ID_MAX_CHARS] or secrets.token_hex(16)
        conversation: AiAssistantConversation | None = (
            db.query(AiAssistantConversation)
            .filter(
                AiAssistantConversation.assistant_id == assistant.id,
                AiAssistantConversation.session_id == normalized_session,
            )
            .first()
        )
        if conversation is not None:
            return conversation
        conversation = AiAssistantConversation(
            user_id=assistant.user_id,
            prospect_id=assistant.prospect_id,
            assistant_id=assistant.id,
            session_id=normalized_session,
            language=(language or "").strip()[:8] or None,
            message_count=0,
        )
        db.add(conversation)
        return conversation

    @staticmethod
    def _counts_since(db: Session, assistant_ids: list[int], since: datetime) -> dict[int, int]:
        rows = (
            db.query(AiAssistantConversation.assistant_id, func.count(AiAssistantConversation.id))
            .filter(
                AiAssistantConversation.assistant_id.in_(assistant_ids),
                AiAssistantConversation.is_test.is_not(True),
                AiAssistantConversation.last_message_at >= since,
            )
            .group_by(AiAssistantConversation.assistant_id)
            .all()
        )
        return dict(rows)


ai_assistant_conversation_service = AiAssistantConversationService()
