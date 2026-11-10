"""The Stripe events of the receptionist's subscriptions, handed over by the core's webhook."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from devleadhunter_receptionist.models.ai_assistant import AiAssistant
from devleadhunter_receptionist.services.assistant_subscription_service import assistant_subscription_service
from devleadhunter_receptionist.services.receptionist_notifications import receptionist_notifications


class ReceptionistStripeEvents:
    """Activates, syncs and flags the receptionist's subscriptions; leaves every other event to the core."""

    async def handle(self, db: Session, event: dict[str, Any]) -> str | None:
        """
        Handle a verified Stripe event when it is one of the receptionist's subscriptions.

        A subscription checkout is the receptionist's when its metadata names one of its subscription rows; a
        lifecycle event or a failed invoice when it resolves to one of them.

        Args:
            db: Active database session.
            event: The verified Stripe event.

        Returns:
            The webhook's message when the event was the receptionist's, None otherwise.
        """
        event_type: str = str(event.get("type", ""))
        event_obj: dict[str, Any] = (event.get("data") or {}).get("object") or {}
        if event_type == "checkout.session.completed" and event_obj.get("mode") == "subscription":
            return await self._activate(db, event_obj)
        if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
            if assistant_subscription_service._record_from_stripe_subscription(db, event_obj) is None:
                return None
            assistant_subscription_service.update_from_stripe_subscription(db, event_obj)
            return "Assistant subscription synced"
        if event_type == "invoice.payment_failed":
            past_due_subscription = assistant_subscription_service.record_payment_failure(db, event_obj)
            if past_due_subscription is None:
                return None
            await receptionist_notifications.notify_assistant_payment_failed(
                db,
                user_id=past_due_subscription.user_id,
                prospect_id=past_due_subscription.prospect_id,
                fallback_name=past_due_subscription.client_name or "Un client",
                invoice_id=event_obj["id"],
            )
            return "Assistant subscription payment failure recorded"
        return None

    @staticmethod
    async def _activate(db: Session, session_obj: dict[str, Any]) -> str | None:
        """Activate the subscription a checkout paid for (once), notify the seller and welcome the business."""
        if assistant_subscription_service._record_from_metadata(db, session_obj.get("metadata")) is None:
            return None
        activated = assistant_subscription_service.activate_from_session(db, session_obj)
        if activated is not None:
            await receptionist_notifications.notify_assistant_subscription(
                db,
                user_id=activated.user_id,
                prospect_id=activated.prospect_id,
                fallback_name=activated.client_name or "Un client",
                amount_cents=activated.amount_cents,
                interval=activated.interval,
            )
            await ReceptionistStripeEvents._welcome_client(db, activated.ai_assistant_id)
        return "Assistant subscription activated"

    @staticmethod
    async def _welcome_client(db: Session, assistant_id: int | None) -> None:
        """Email the business that just subscribed its install line and its client-space link; never fails the webhook."""
        from devleadhunter_receptionist.services.client_space_service import ai_assistant_client_space_service

        if assistant_id is None:
            return
        assistant = db.get(AiAssistant, assistant_id)
        if assistant is not None:
            await ai_assistant_client_space_service.try_send_welcome(db, assistant)


receptionist_stripe_events = ReceptionistStripeEvents()
