"""Routes of the assistant subscriptions: the owner's list, cancellation and refund, the permanent subscription link,
and the public page that opens Stripe Checkout from it.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.v1.routes.ai_assistant_common import (
    client_ip,
    demo_url,
    owned_assistant_or_404,
)
from core.database import get_db
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from models.user import User
from schemas.ai_assistant import (
    AssistantSubscriptionItem,
    AssistantSubscriptionListResponse,
)
from services.ai_assistant.assistant_service import ai_assistant_service
from services.assistant_subscription_service import assistant_subscription_service
from services.auth_service import get_current_active_user
from services.rate_limiter import (
    assistant_subscribe_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistant-subscriptions"])


def _to_subscription_item(
    subscription: object, business_name: str | None, assistant_name: str | None
) -> AssistantSubscriptionItem:
    """Build the API item from a subscription row + its assistant's names."""
    return AssistantSubscriptionItem(
        id=subscription.id,
        ai_assistant_id=subscription.ai_assistant_id,
        prospect_id=subscription.prospect_id,
        business_name=business_name,
        assistant_name=assistant_name,
        client_name=subscription.client_name,
        client_email=subscription.client_email,
        interval=subscription.interval,
        amount_cents=subscription.amount_cents,
        currency=subscription.currency,
        status=subscription.status,
        current_period_end=subscription.current_period_end,
        canceled_at=subscription.canceled_at,
        stripe_subscription_id=subscription.stripe_subscription_id,
        created_at=subscription.created_at,
    )


@router.get("/subscriptions", response_model=AssistantSubscriptionListResponse)
async def list_assistant_subscriptions(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AssistantSubscriptionListResponse:
    """List the caller's assistant subscriptions + the headline KPIs (active count, MRR)."""
    rows = assistant_subscription_service.list_for_user(db, user.id)
    active_count, mrr_cents = assistant_subscription_service.stats_for_user(db, user.id)
    return AssistantSubscriptionListResponse(
        subscriptions=[
            _to_subscription_item(subscription, business_name, assistant_name)
            for subscription, business_name, assistant_name in rows
        ],
        active_count=active_count,
        mrr_cents=mrr_cents,
    )


@router.post("/subscriptions/{subscription_id}/cancel", response_model=AssistantSubscriptionItem)
async def cancel_assistant_subscription(
    subscription_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AssistantSubscriptionItem:
    """Cancel one of the caller's subscriptions (immediately, on Stripe + locally)."""
    subscription = assistant_subscription_service.get_owned(db, subscription_id, user.id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement introuvable.")
    try:
        assistant_subscription_service.cancel(db, subscription)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Assistant subscription cancel failed for %s", subscription_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe indisponible pour annuler."
        ) from exc
    assistant = db.get(AiAssistant, subscription.ai_assistant_id) if subscription.ai_assistant_id else None
    return _to_subscription_item(
        subscription, getattr(assistant, "business_name", None), getattr(assistant, "assistant_name", None)
    )


@router.post("/subscriptions/{subscription_id}/refund", status_code=status.HTTP_204_NO_CONTENT)
async def refund_assistant_subscription(
    subscription_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """Refund the subscription's latest payment (« satisfait-remboursé »)."""
    subscription = assistant_subscription_service.get_owned(db, subscription_id, user.id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement introuvable.")
    try:
        assistant_subscription_service.refund_last_payment(db, subscription)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Assistant subscription refund failed for %s", subscription_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe indisponible pour rembourser."
        ) from exc


@router.get("/{assistant_id}/subscription/link")
async def get_assistant_subscription_link(
    assistant_id: int,
    interval: str = "month",
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    The permanent subscription link (monthly or annual) the owner sends to the client.

    It never expires: each click opens a fresh Stripe Checkout on the public ``subscribe`` endpoint,
    at the price configured at that moment (locked once the client pays).
    """
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    if assistant.status == AiAssistantStatus.DELIVERED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cet assistant est déjà vendu.")
    if assistant.status not in (AiAssistantStatus.ACTIVE.value, AiAssistantStatus.EXPIRED.value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="L'assistant doit être actif.")
    if interval not in ("month", "year"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Intervalle invalide (month ou year).")
    return {"url": assistant_subscription_service.subscription_link(assistant, interval)}


@router.get("/public/{slug}/subscribe")
async def subscribe_to_assistant(
    slug: str,
    request: Request,
    interval: str = "month",
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Open a fresh Stripe Checkout for a client clicking the permanent subscription link.

    A live or expired demo can be subscribed to (the payment revives an expired one); an assistant
    already sold sends the client to its page instead of a second checkout.
    """
    if not assistant_subscribe_limiter.allow(f"{slug}:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de tentatives, réessayez plus tard"
        )
    assistant = ai_assistant_service.get_by_slug(db, slug)
    if assistant is None or assistant.status not in (
        AiAssistantStatus.ACTIVE.value,
        AiAssistantStatus.EXPIRED.value,
        AiAssistantStatus.DELIVERED.value,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    if assistant.status == AiAssistantStatus.DELIVERED.value:
        return RedirectResponse(url=demo_url(assistant.slug), status_code=status.HTTP_303_SEE_OTHER)
    if interval not in ("month", "year"):
        interval = "month"
    try:
        checkout_url = assistant_subscription_service.create_checkout_session(
            db,
            user_id=assistant.user_id,
            assistant=assistant,
            interval=interval,
            success_url=f"{demo_url(assistant.slug)}?subscribed=1",
            cancel_url=demo_url(assistant.slug),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Assistant subscription checkout failed for slug %s", slug)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe indisponible pour le moment."
        ) from exc
    return RedirectResponse(url=checkout_url, status_code=status.HTTP_303_SEE_OTHER)
