"""AI-assistant subscription lifecycle statuses (mirror of the Stripe subscription statuses we care about)."""

from enum import Enum


class AiAssistantSubscriptionStatus(str, Enum):
    """Status of a sold AI-assistant subscription."""

    # Checkout created but not yet paid (Stripe ``incomplete``) — nothing to activate yet.
    INCOMPLETE = "incomplete"
    # Paid and running (Stripe ``active``/``trialing``) — the client is billed each period.
    ACTIVE = "active"
    # A renewal charge failed (Stripe ``past_due``/``unpaid``) — Stripe dunning is retrying.
    PAST_DUE = "past_due"
    # Ended (Stripe ``canceled``) — the client stopped, or an annual term lapsed without renewal.
    CANCELED = "canceled"


# A paying client: running, or a renewal charge being retried by Stripe.
LIVE_SUBSCRIPTION_STATUSES: tuple[str, ...] = (
    AiAssistantSubscriptionStatus.ACTIVE.value,
    AiAssistantSubscriptionStatus.PAST_DUE.value,
)
