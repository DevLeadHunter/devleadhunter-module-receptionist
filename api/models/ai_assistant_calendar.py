"""The Google agenda a sold assistant books appointments into, connected by its client."""

from datetime import datetime

from sqlalchemy import JSON, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import UTF8MB4_TABLE_OPTIONS, Base
from enums.assistant_calendar_status import AssistantCalendarStatus


class AiAssistantCalendar(Base):
    """One agenda per assistant: the client's Google tokens (encrypted) and the booking settings.

    The client connects it from the client space; the assistant then offers its free slots in the widget
    and creates the booked appointments in it. ``NULL`` settings read as their defaults.
    """

    __tablename__ = "ai_assistant_calendars"
    __table_args__ = (
        UniqueConstraint("assistant_id", name="uq_ai_assistant_calendars_assistant"),
        UTF8MB4_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    assistant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False, default="google")
    # The connected Google account, shown in the client space.
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Encrypted with ``encryption_service`` (Fernet), never returned by any endpoint.
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # « primary » is the account's main agenda; any agenda id the account can write to works.
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False, default="primary")
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_notice_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Kinds of appointment the visitor picks from (« Révision », « Contrôle technique »), in order.
    appointment_types_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=AssistantCalendarStatus.CONNECTED.value)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
