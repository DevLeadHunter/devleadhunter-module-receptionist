"""Recurring subscription for a sold AI assistant (Stripe).

One row per subscription a client takes on a prospect's assistant. **Grandfathering**: ``amount_cents``
and ``interval`` are LOCKED at subscription time — raising the user's configured price later never
touches an existing row (and the Stripe subscription keeps its own price too). So a client who
subscribed at 29 €/mois stays at 29 € even after the launch price rises.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from enums.assistant_subscription_status import AssistantSubscriptionStatus


class AiAssistantSubscription(Base):
    """A client's recurring subscription to a sold AI assistant."""

    __tablename__ = "ai_assistant_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # The seller (the DevLeadHunter user who owns the assistant and gets paid).
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # The buyer's prospect + the assistant being subscribed to (both nullable: the prospect/assistant
    # could be deleted while the subscription lives on Stripe).
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ai_assistant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Stripe artifacts.
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Plan — LOCKED at subscription creation (grandfathering).
    interval: Mapped[str] = mapped_column(String(8), nullable=False, default="month")  # "month" | "year"
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="eur")

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AssistantSubscriptionStatus.INCOMPLETE.value, index=True
    )
    # End of the paid period (renews monthly/annually); NULL until the first payment.
    current_period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # When the first payment activated it (naive UTC): the start of the service. NULL on rows activated
    # before the column existed — ``created_at`` (the checkout) stands in.
    activated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Buyer identity, denormalised (from the Stripe Checkout customer).
    client_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(default=None, onupdate=datetime.utcnow, nullable=True)
