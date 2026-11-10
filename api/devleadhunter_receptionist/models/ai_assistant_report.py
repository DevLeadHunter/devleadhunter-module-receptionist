"""The monthly report of a sold assistant: what it brought its client over a calendar month."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import UTF8MB4_TABLE_OPTIONS, Base


class AiAssistantReport(Base):
    """One month of a sold assistant, as reported to its client (and copied to the operator).

    The row is written before anything is sent (one per assistant and month) and each send attempt is
    claimed on it: two passes never send the same report twice. ``stats_json`` keeps the figures.
    """

    __tablename__ = "ai_assistant_reports"
    __table_args__ = (
        UniqueConstraint("assistant_id", "month", name="uq_ai_assistant_reports_assistant_month"),
        UTF8MB4_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    assistant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # The reported month, « YYYY-MM » (Paris calendar).
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    stats_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # No conversation and no request all month: the churn signal.
    is_empty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    # Send attempts (at most three, an hour apart); ``sent_at`` stays NULL until one succeeds.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
