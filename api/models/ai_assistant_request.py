"""A structured request a visitor left through an AI assistant — the unit the business owner handles."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import UTF8MB4_TABLE_OPTIONS, Base
from enums.ai_assistant_request import AiAssistantRequestChannel, AiAssistantRequestStatus, AiAssistantRequestType


class AiAssistantRequest(Base):
    """A visitor's request: who, what they need (typed and summarized), when, and its handling status.

    One per widget session — a visitor who leaves their details twice updates the same request.
    It replaces ``AiAssistantLead`` for new captures; the legacy leads are copied in once
    (``legacy_lead_id``) and their table is kept read-only.
    """

    __tablename__ = "ai_assistant_requests"
    __table_args__ = (
        Index("ix_ai_assistant_requests_assistant_session", "assistant_id", "session_id"),
        UTF8MB4_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    assistant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Journal link (ai_assistant_conversations) and the widget session that identifies the visitor.
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False, default=AiAssistantRequestType.OTHER.value)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AiAssistantRequestStatus.NEW.value, index=True
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default=AiAssistantRequestChannel.SITE.value)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact: Mapped[str] = mapped_column(String(255), nullable=False)
    # The visitor's own words, and the owner-facing summary written from them and the conversation.
    need: Mapped[str | None] = mapped_column(Text, nullable=True)
    need_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    photos_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Half-days wished for an appointment (« [{"date": "2026-09-28", "period": "morning"}] »), picked in the widget.
    appointment_slots_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # NULL when the business hours are unknown — never counted as « hors horaires » by default.
    received_outside_hours: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Left from a « ?internal=1 » visit (the operator testing): recorded, never announced, out of the KPIs.
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    owner_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    owner_notified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # When the business owner's alerts were routed (sold assistant only): reminders follow from it.
    owner_alerted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Owner SMS: when it may go (held to the end of the night window), then when it went — at most one.
    sms_due_at: Mapped[datetime | None] = mapped_column(nullable=True)
    sms_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # The single J+1 reminder to the owner, and the 48 h « still waiting » push to the operator.
    reminder_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    stale_notified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    legacy_lead_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
