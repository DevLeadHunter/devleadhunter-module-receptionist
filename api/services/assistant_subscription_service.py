"""Recurring Stripe subscriptions for sold AI assistants.

The seller generates a subscription checkout link for a prospect's assistant and sends it; the client
subscribes on Stripe's hosted page (``mode="subscription"``). **Grandfathering**: the price is LOCKED
on the local row at creation (and Stripe keeps the subscription's own price), so raising the configured
price later never touches an existing subscriber.

⚠️ Runs on the **platform** Stripe account (``STRIPE_SECRET_KEY``), like the credits purchase — the
right choice for a solo seller, whose Stripe *is* the platform account. A multi-tenant setup would
move this to each user's **connected** account (Stripe Connect subscriptions with an application fee),
mirroring the website invoice path (:mod:`services.payment_providers.stripe_provider`).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import stripe
from sqlalchemy.orm import Session

from core.config import settings
from enums.assistant_subscription_status import AssistantSubscriptionStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_subscription import AiAssistantSubscription
from services.assistant_pricing_service import AssistantPricingService

logger = logging.getLogger(__name__)

# Stripe subscription statuses → our own. Anything unmapped leaves the record's status unchanged.
_STRIPE_STATUS_MAP: dict[str, str] = {
    "active": AssistantSubscriptionStatus.ACTIVE.value,
    "trialing": AssistantSubscriptionStatus.ACTIVE.value,
    "past_due": AssistantSubscriptionStatus.PAST_DUE.value,
    "unpaid": AssistantSubscriptionStatus.PAST_DUE.value,
    "canceled": AssistantSubscriptionStatus.CANCELED.value,
    "incomplete_expired": AssistantSubscriptionStatus.CANCELED.value,
    "incomplete": AssistantSubscriptionStatus.INCOMPLETE.value,
}


class AssistantSubscriptionService:
    """Create + track recurring subscriptions to sold AI assistants (platform Stripe account)."""

    def __init__(self) -> None:
        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key
        self._stripe = stripe

    def create_checkout_session(
        self,
        db: Session,
        *,
        user_id: int,
        assistant: AiAssistant,
        interval: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """
        Create a Stripe subscription Checkout Session and return its hosted URL.

        The price is resolved + LOCKED now (grandfathering): a local ``INCOMPLETE`` row is created with
        the amount, and the webhook flips it to ``ACTIVE`` once the client pays.

        Args:
            db: Active database session.
            user_id: The seller (assistant owner).
            assistant: The assistant being subscribed to.
            interval: ``"month"`` or ``"year"``.
            success_url: Where Stripe returns the client after paying.
            cancel_url: Where Stripe returns the client if they abandon.

        Returns:
            The hosted Stripe Checkout URL to send to the client.

        Raises:
            ValueError: when Stripe is not configured.
        """
        if not settings.stripe_secret_key:
            raise ValueError("STRIPE_SECRET_KEY is not configured.")

        if interval == "year":
            amount_cents = AssistantPricingService.annual_price_cents(db, user_id)
            recurring = {"interval": "year"}
            label = "annuel"
        else:
            interval = "month"
            amount_cents = AssistantPricingService.monthly_price_cents(db, user_id)
            recurring = {"interval": "month"}
            label = "mensuel"

        record = AiAssistantSubscription(
            user_id=user_id,
            prospect_id=assistant.prospect_id,
            ai_assistant_id=assistant.id,
            interval=interval,
            amount_cents=amount_cents,
            currency="eur",
            status=AssistantSubscriptionStatus.INCOMPLETE.value,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        session = self._stripe.checkout.Session.create(
            mode="subscription",
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {"name": f"Assistant IA — {assistant.business_name} ({label})"},
                        "unit_amount": amount_cents,
                        "recurring": recurring,
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(record.id),
            metadata={
                "assistant_subscription_id": str(record.id),
                "user_id": str(user_id),
                "assistant_id": str(assistant.id),
            },
            subscription_data={"metadata": {"assistant_subscription_id": str(record.id)}},
        )
        record.stripe_checkout_session_id = session.id
        db.commit()
        return session.url

    def activate_from_session(self, db: Session, session_obj: dict) -> None:
        """
        Webhook ``checkout.session.completed`` (subscription mode): mark the record active.

        Args:
            db: Active database session.
            session_obj: The Stripe Checkout Session payload.
        """
        record = self._record_from_metadata(db, session_obj.get("metadata"))
        if record is None:
            return
        record.stripe_subscription_id = session_obj.get("subscription")
        record.stripe_customer_id = session_obj.get("customer")
        details = session_obj.get("customer_details") or {}
        record.client_email = details.get("email") or record.client_email
        record.client_name = details.get("name") or record.client_name
        record.status = AssistantSubscriptionStatus.ACTIVE.value
        db.commit()
        logger.info("[AssistantSub] Activated subscription record %s (assistant %s)", record.id, record.ai_assistant_id)

    def update_from_stripe_subscription(self, db: Session, sub_obj: dict) -> None:
        """
        Webhook ``customer.subscription.updated`` / ``.deleted``: sync status + period end.

        Args:
            db: Active database session.
            sub_obj: The Stripe Subscription payload.
        """
        record = self._record_from_stripe_subscription(db, sub_obj)
        if record is None:
            return
        record.status = _STRIPE_STATUS_MAP.get(str(sub_obj.get("status")), record.status)
        period_end = sub_obj.get("current_period_end")
        if period_end:
            record.current_period_end = datetime.fromtimestamp(int(period_end), UTC)
        if record.status == AssistantSubscriptionStatus.CANCELED.value and record.canceled_at is None:
            record.canceled_at = datetime.now(UTC)
        db.commit()

    def is_active_for_assistant(self, db: Session, assistant_id: int) -> bool:
        """Whether the assistant has a paid, running subscription."""
        return (
            db.query(AiAssistantSubscription)
            .filter(
                AiAssistantSubscription.ai_assistant_id == assistant_id,
                AiAssistantSubscription.status == AssistantSubscriptionStatus.ACTIVE.value,
            )
            .first()
            is not None
        )

    @staticmethod
    def _record_from_metadata(db: Session, metadata: dict | None) -> AiAssistantSubscription | None:
        """Resolve a local subscription row from a Stripe object's ``metadata.assistant_subscription_id``."""
        record_id = (metadata or {}).get("assistant_subscription_id")
        if not record_id:
            return None
        try:
            return db.get(AiAssistantSubscription, int(record_id))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _record_from_stripe_subscription(cls, db: Session, sub_obj: dict) -> AiAssistantSubscription | None:
        """Resolve a local row from a Stripe Subscription (by metadata, then by the subscription id)."""
        record = cls._record_from_metadata(db, sub_obj.get("metadata"))
        if record is not None:
            return record
        sub_id = sub_obj.get("id")
        if not sub_id:
            return None
        return (
            db.query(AiAssistantSubscription).filter(AiAssistantSubscription.stripe_subscription_id == sub_id).first()
        )


assistant_subscription_service = AssistantSubscriptionService()
