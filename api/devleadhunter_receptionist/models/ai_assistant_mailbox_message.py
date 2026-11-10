"""A Gmail message a receptionist already read: its ids and what became of it, never its content."""

from datetime import datetime

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.clock import naive_utc_now
from core.database import UTF8MB4_TABLE_OPTIONS, Base
from enums.ai_assistant_mailbox import AiAssistantMailboxMessageOutcome


class AiAssistantMailboxMessage(Base):
    """One email of a connected mailbox, read once: no email is read twice nor answered with two drafts.

    The rows are forgotten after 90 days; the drafted ones count the drafts of the month and link the thread to the
    request it opened, so a reply sent from Gmail closes it.
    """

    __tablename__ = "ai_assistant_mailbox_messages"
    __table_args__ = (
        UniqueConstraint("assistant_id", "gmail_message_id", name="uq_ai_assistant_mailbox_messages_message"),
        UTF8MB4_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    assistant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    gmail_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    gmail_thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AiAssistantMailboxMessageOutcome.SKIPPED.value
    )
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Failed reads of the email so far (the model or Gmail unavailable).
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(default=naive_utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=naive_utc_now, onupdate=naive_utc_now, nullable=False)
