"""The Gmail mailbox a sold receptionist reads to prepare reply drafts, connected by its client."""

from datetime import date, datetime

from sqlalchemy import Date, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.clock import naive_utc_now
from core.database import UTF8MB4_TABLE_OPTIONS, Base
from enums.ai_assistant_mailbox import AiAssistantMailboxStatus


class AiAssistantMailbox(Base):
    """One mailbox per assistant: the client's Google tokens (encrypted) and where its reading stands.

    The client connects it from the client space; every few minutes the receptionist reads the new customer emails
    and leaves a reply to each as a draft in the same thread, which the business sends itself.
    """

    __tablename__ = "ai_assistant_mailboxes"
    __table_args__ = (
        UniqueConstraint("assistant_id", name="uq_ai_assistant_mailboxes_assistant"),
        UTF8MB4_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    assistant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False, default="gmail")
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Encrypted with ``encryption_service`` (Fernet), never returned by any endpoint.
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Gmail's history id up to which every new email was read.
    history_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=AiAssistantMailboxStatus.CONNECTED.value)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The business day (Paris) the daily cap stopped the reading.
    capped_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(default=naive_utc_now, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=naive_utc_now, onupdate=naive_utc_now, nullable=False)
