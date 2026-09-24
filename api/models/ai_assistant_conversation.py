"""A visitor's conversation with an AI assistant, journaled server-side (what visitors ask, proof of value)."""

from datetime import datetime

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class AiAssistantConversation(Base):
    """One visitor's conversation with an assistant, identified by the session id the widget generates."""

    __tablename__ = "ai_assistant_conversations"
    __table_args__ = (Index("ix_ai_assistant_conversations_assistant_session", "assistant_id", "session_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    assistant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Random id the widget keeps with the visitor's conversation, so every turn lands in the same row.
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # From a « ?internal=1 » visit (the operator testing): journaled, out of the counts and reports. NULL = False.
    is_test: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False, index=True)
    last_message_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False, index=True)

    messages: Mapped[list["AiAssistantMessage"]] = relationship(  # noqa: F821 — resolved by the mapper registry
        "AiAssistantMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AiAssistantMessage.id",
    )
