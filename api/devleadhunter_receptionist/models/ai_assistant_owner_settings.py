"""The receptionist price a user charges, kept by the module instead of on the core's user row."""

from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.clock import naive_utc_now
from core.database import Base


class AiAssistantOwnerSettings(Base):
    """
    The CURRENT receptionist price of one user, for the subscriptions sold from now on.

    No foreign key to ``users``: purging a user never trips on it, and a missing row reads as the defaults.
    """

    __tablename__ = "ai_assistant_owner_settings"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    monthly_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=7900)
    annual_free_months: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=naive_utc_now)

    def __repr__(self) -> str:
        """String representation of the settings."""
        return f"<AiAssistantOwnerSettings user_id={self.user_id} monthly={self.monthly_price_cents}>"
