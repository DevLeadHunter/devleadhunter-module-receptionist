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
from datetime import UTC, datetime, timedelta

import stripe
from sqlalchemy.orm import Session

from core.config import settings
from enums.ai_assistant_status import AiAssistantStatus
from enums.assistant_subscription_status import AssistantSubscriptionStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_subscription import AiAssistantSubscription
from services.assistant_pricing_service import AssistantPricingService

logger = logging.getLogger(__name__)

# An unpaid checkout row is reused by later clicks on the permanent link, then purged once stale.
_INCOMPLETE_ROW_TTL_DAYS = 7

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

    @staticmethod
    def subscription_link(assistant: AiAssistant, interval: str) -> str:
        """
        The permanent link the seller sends a client: it opens a fresh Stripe Checkout at each click.

        A Checkout Session expires 24 h after creation (Stripe's maximum), so the emailed link must
        not be one — it targets the public ``subscribe`` endpoint, which creates the session on demand.

        Args:
            assistant: The assistant being sold.
            interval: ``"month"`` or ``"year"``.

        Returns:
            The absolute API URL to send.
        """
        base: str = settings.api_base_url.rstrip("/")
        return f"{base}/api/v1/ai-assistants/public/{assistant.slug}/subscribe?interval={interval}"

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

        The price is resolved + LOCKED now (grandfathering): a local ``INCOMPLETE`` row carries the
        amount — the recent unpaid row of this assistant is reused, so repeated clicks on the permanent
        link never pile up rows — and the webhook flips it to ``ACTIVE`` once the client pays.

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

        record = self._reusable_incomplete_row(db, assistant_id=assistant.id, interval=interval)
        if record is None:
            record = AiAssistantSubscription(
                user_id=user_id,
                prospect_id=assistant.prospect_id,
                ai_assistant_id=assistant.id,
                interval=interval,
                currency="eur",
                status=AssistantSubscriptionStatus.INCOMPLETE.value,
            )
            db.add(record)
        # Unpaid, so nothing to grandfather yet: the row follows the price configured at this click.
        record.amount_cents = amount_cents
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

    def activate_from_session(self, db: Session, session_obj: dict) -> AiAssistantSubscription | None:
        """
        Webhook ``checkout.session.completed`` (subscription mode): mark the record active.

        Args:
            db: Active database session.
            session_obj: The Stripe Checkout Session payload.

        Returns:
            The record when this call **freshly** activated it (so the caller notifies the seller once),
            or None when there is no matching record or it was already active (idempotent retry).
        """
        record = self._record_from_metadata(db, session_obj.get("metadata"))
        if record is None:
            return None
        was_already_active = record.status == AssistantSubscriptionStatus.ACTIVE.value
        record.stripe_subscription_id = session_obj.get("subscription")
        record.stripe_customer_id = session_obj.get("customer")
        details = session_obj.get("customer_details") or {}
        record.client_email = details.get("email") or record.client_email
        record.client_name = details.get("name") or record.client_name
        record.status = AssistantSubscriptionStatus.ACTIVE.value
        # Stamped here even when a subscription update already flipped the row to active (events are unordered).
        if record.activated_at is None:
            record.activated_at = datetime.now(UTC).replace(tzinfo=None)
        # The client is now paying: mark the assistant SOLD so the demo TTL never takes it down.
        self._mark_assistant_sold(db, record.ai_assistant_id)
        db.commit()
        logger.info("[AssistantSub] Activated subscription record %s (assistant %s)", record.id, record.ai_assistant_id)
        return None if was_already_active else record

    @staticmethod
    def _reusable_incomplete_row(db: Session, *, assistant_id: int, interval: str) -> AiAssistantSubscription | None:
        """The assistant's recent unpaid checkout row for this interval, or None."""
        cutoff: datetime = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=_INCOMPLETE_ROW_TTL_DAYS)
        return (
            db.query(AiAssistantSubscription)
            .filter(
                AiAssistantSubscription.ai_assistant_id == assistant_id,
                AiAssistantSubscription.interval == interval,
                AiAssistantSubscription.status == AssistantSubscriptionStatus.INCOMPLETE.value,
                AiAssistantSubscription.created_at >= cutoff,
            )
            .order_by(AiAssistantSubscription.created_at.desc())
            .first()
        )

    def purge_stale_incomplete_rows(self, db: Session) -> int:
        """Delete the unpaid checkout rows older than the reuse window (the client never paid).

        Returns:
            The number of rows deleted.
        """
        cutoff: datetime = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=_INCOMPLETE_ROW_TTL_DAYS)
        stale: list[AiAssistantSubscription] = (
            db.query(AiAssistantSubscription)
            .filter(
                AiAssistantSubscription.status == AssistantSubscriptionStatus.INCOMPLETE.value,
                AiAssistantSubscription.created_at < cutoff,
            )
            .all()
        )
        for row in stale:
            db.delete(row)
        if stale:
            db.commit()
        return len(stale)

    @staticmethod
    def _mark_assistant_sold(db: Session, assistant_id: int | None) -> None:
        """Promote a subscribed assistant to DELIVERED: sold, so never expired by the demo cleanup.

        An expired demo is revived by the payment — a client who pays always gets their assistant.
        """
        if not assistant_id:
            return
        assistant = db.get(AiAssistant, assistant_id)
        if assistant is None:
            return
        if assistant.status in (AiAssistantStatus.ACTIVE.value, AiAssistantStatus.EXPIRED.value):
            assistant.status = AiAssistantStatus.DELIVERED.value

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

    def active_by_assistant_ids(self, db: Session, assistant_ids: list[int]) -> dict[int, AiAssistantSubscription]:
        """Active subscriptions for the given assistants, keyed by assistant id (for the dashboard list)."""
        if not assistant_ids:
            return {}
        rows = (
            db.query(AiAssistantSubscription)
            .filter(
                AiAssistantSubscription.ai_assistant_id.in_(assistant_ids),
                AiAssistantSubscription.status == AssistantSubscriptionStatus.ACTIVE.value,
            )
            .all()
        )
        return {row.ai_assistant_id: row for row in rows if row.ai_assistant_id is not None}

    def list_for_user(self, db: Session, user_id: int) -> list[tuple[AiAssistantSubscription, str | None, str | None]]:
        """All of the user's subscriptions (newest first) with their assistant's names, for the Ventes page."""
        return (
            db.query(AiAssistantSubscription, AiAssistant.business_name, AiAssistant.assistant_name)
            .outerjoin(AiAssistant, AiAssistant.id == AiAssistantSubscription.ai_assistant_id)
            .filter(AiAssistantSubscription.user_id == user_id)
            .order_by(AiAssistantSubscription.created_at.desc())
            .all()
        )

    def stats_for_user(self, db: Session, user_id: int) -> tuple[int, int]:
        """
        Return ``(active_count, mrr_cents)`` — the MRR normalises an annual plan to its monthly share.

        Args:
            db: Active database session.
            user_id: Owner of the subscriptions.

        Returns:
            The active-subscription count and the monthly recurring revenue in cents.
        """
        active = (
            db.query(AiAssistantSubscription)
            .filter(
                AiAssistantSubscription.user_id == user_id,
                AiAssistantSubscription.status == AssistantSubscriptionStatus.ACTIVE.value,
            )
            .all()
        )
        mrr_cents = sum((row.amount_cents // 12 if row.interval == "year" else row.amount_cents) for row in active)
        return len(active), mrr_cents

    def get_owned(self, db: Session, subscription_id: int, user_id: int) -> AiAssistantSubscription | None:
        """Fetch a subscription that belongs to the user (for a detail/cancel/refund action)."""
        return (
            db.query(AiAssistantSubscription)
            .filter(AiAssistantSubscription.id == subscription_id, AiAssistantSubscription.user_id == user_id)
            .first()
        )

    def cancel(self, db: Session, subscription: AiAssistantSubscription) -> AiAssistantSubscription:
        """
        Cancel the subscription on Stripe (immediately) and mark the local row canceled.

        A row that never reached Stripe (``INCOMPLETE``) is just closed locally. Raises when the Stripe
        cancel fails, so the operator sees it rather than a silently-inconsistent state.

        Args:
            db: Active database session.
            subscription: The subscription to cancel.

        Returns:
            The updated subscription.

        Raises:
            ValueError: when Stripe is needed but not configured.
        """
        if subscription.stripe_subscription_id:
            if not settings.stripe_secret_key:
                raise ValueError("Stripe non configuré.")
            self._stripe.Subscription.cancel(subscription.stripe_subscription_id)
        subscription.status = AssistantSubscriptionStatus.CANCELED.value
        subscription.canceled_at = subscription.canceled_at or datetime.now(UTC)
        db.commit()
        db.refresh(subscription)
        return subscription

    def refund_last_payment(self, db: Session, subscription: AiAssistantSubscription) -> None:
        """
        Refund the subscription's latest invoice (the « satisfait-remboursé » gesture).

        Since the 2025-03-31 Stripe API the Invoice no longer carries ``payment_intent`` or ``charge``:
        the payment is read from ``payments.data.payment.payment_intent`` and refunded by
        PaymentIntent; older accounts fall back to the invoice charge, found via the customer.

        Args:
            db: Active database session (unused, kept for a consistent signature).
            subscription: The subscription whose last invoice to refund.

        Raises:
            ValueError: when there is no Stripe payment to refund.
        """
        if not subscription.stripe_subscription_id or not settings.stripe_secret_key:
            raise ValueError("Aucun paiement Stripe à rembourser.")
        sub = self._stripe.Subscription.retrieve(subscription.stripe_subscription_id)
        invoice_id = self._object_id(sub.get("latest_invoice"))
        if not invoice_id:
            raise ValueError("Aucun paiement à rembourser.")
        payment_intent_id = self._invoice_payment_intent_id(invoice_id)
        if payment_intent_id:
            self._stripe.Refund.create(payment_intent=payment_intent_id)
            return
        charge_id = self._invoice_charge_id(invoice_id)
        if not charge_id:
            raise ValueError("Aucun paiement à rembourser.")
        self._stripe.Refund.create(charge=charge_id)

    def _invoice_payment_intent_id(self, invoice_id: str) -> str | None:
        """The PaymentIntent that settled an invoice, or None when the API version exposes none."""
        try:
            invoice = self._stripe.Invoice.retrieve(invoice_id, expand=["payments.data.payment.payment_intent"])
        except self._stripe.error.InvalidRequestError:
            return None
        direct = self._object_id(invoice.get("payment_intent"))
        if direct:
            return direct
        payments = invoice.get("payments") or {}
        entries = payments.get("data", []) if isinstance(payments, dict) else []
        for entry in entries or []:
            payment_intent_id = self._object_id((entry.get("payment") or {}).get("payment_intent"))
            if payment_intent_id:
                return payment_intent_id
        return None

    def _invoice_charge_id(self, invoice_id: str) -> str | None:
        """The paid, un-refunded charge of an invoice, via its customer when the Invoice hides it."""
        invoice = self._stripe.Invoice.retrieve(invoice_id)
        direct = self._object_id(invoice.get("charge"))
        if direct:
            return direct
        customer_id = self._object_id(invoice.get("customer"))
        if not customer_id:
            return None
        charges = self._stripe.Charge.list(customer=customer_id, limit=100)
        for charge in charges.get("data", []) or []:
            settles_invoice = self._object_id(charge.get("invoice")) == invoice_id
            if settles_invoice and charge.get("paid") and not charge.get("refunded"):
                return charge.get("id")
        return None

    @staticmethod
    def _object_id(value: object) -> str | None:
        """The id of a Stripe field that is either an id string or an expanded object."""
        if isinstance(value, dict):
            return value.get("id")
        return value if isinstance(value, str) else None

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
