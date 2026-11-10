"""An appointment a visitor booked through a sold assistant, in its client's Google agenda."""

from datetime import datetime

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import UTF8MB4_TABLE_OPTIONS, Base


class AiAssistantAppointment(Base):
    """A booked slot: its request, its Google event, and the visitor's confirmation and J-1 reminder.

    Times are naive UTC. The confirmation and the reminder are each claimed on the row before they leave:
    two passes never send them twice.
    """

    __tablename__ = "ai_assistant_appointments"
    __table_args__ = (
        Index("ix_ai_assistant_appointments_assistant_start", "assistant_id", "starts_at"),
        UTF8MB4_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    assistant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # One appointment per request: the database guarantees it, whatever the process lock misses.
    request_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    starts_at: Mapped[datetime] = mapped_column(nullable=False)
    ends_at: Mapped[datetime] = mapped_column(nullable=False)
    type_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The Google event, once created (our own id, so a retry never books twice).
    google_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Where the visitor is told: a mobile in E.164 (SMS) and/or an email address.
    visitor_phone_e164: Mapped[str | None] = mapped_column(String(20), nullable=True)
    visitor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Booked from a « ?internal=1 » visit (the operator testing).
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    confirmation_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # NULL when the booking is too close to the appointment for a reminder to make sense.
    reminder_due_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
