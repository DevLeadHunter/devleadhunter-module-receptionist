"""AI assistant lead model — a visitor left their details through a prospect's assistant."""

from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class AiAssistantLead(Base):
    """A qualified lead a visitor left through an AI assistant (name + contact + need).

    Kept durably and attached to the prospect, like ``DemoSiteLead``: a visitor's own words
    and contact are business data, not just a transient notification.
    """

    __tablename__ = "ai_assistant_leads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    assistant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact: Mapped[str] = mapped_column(String(255), nullable=False)
    need: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
