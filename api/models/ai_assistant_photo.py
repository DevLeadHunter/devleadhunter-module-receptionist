"""A photo a visitor sent through an AI assistant for a quote, with what the vision model saw in it."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class AiAssistantPhoto(Base):
    """A visitor's photo: stored on R2 under an unguessable key for 90 days, described by the vision model.

    Sent before the visitor leaves their details, it belongs to the widget session; the request captured
    for that session then links it (``request_id``) and lists it in ``photos_json``. An off-topic photo is
    deleted from storage at once: only its row remains, without key nor URL.
    """

    __tablename__ = "ai_assistant_photos"
    __table_args__ = (Index("ix_ai_assistant_photos_assistant_session", "assistant_id", "session_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    assistant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # NULL when the vision model could not look at it; False for an off-topic photo (refused).
    relevant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    object_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    damage: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ``AiAssistantPhotoUrgency`` value.
    urgency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    missing_questions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # What the assistant answered the visitor about the photo.
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False, index=True)
    # When the image left storage (off-topic at once, or after the 90-day retention).
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
