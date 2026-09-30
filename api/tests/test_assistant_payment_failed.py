"""
A refused payment of a receptionist subscription (Stripe ``invoice.payment_failed``): the subscription goes past due at
once and the operator is told once per invoice, however often Stripe replays the event.
"""

import asyncio
from typing import Any

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import api.v1.routes.payments as payment_routes
import migrations.add_assistant_subscription_payment_failed_invoice_id as payment_failed_migration
import services.notification_service as notification_module
import services.stripe_payment_service as stripe_payment_module
from enums.ai_assistant_subscription_status import AiAssistantSubscriptionStatus
from models.ai_assistant_subscription import AiAssistantSubscription
from models.prospect_db import ProspectDB
from services.notification_service import notification_service


class _VerifiedStripe:
    """The webhook's Stripe service: every signature holds, and no event is a credits purchase."""

    def __init__(self, event: dict[str, Any]) -> None:
        self.event = event

    def verify_webhook_signature(self, payload: bytes, signature: str) -> dict[str, Any]:
        return self.event

    def handle_webhook_event(self, db: Session, event: dict[str, Any]) -> bool:
        return False


class _WebhookDelivery:
    """A Stripe delivery as the webhook reads it: only its raw body."""

    async def body(self) -> bytes:
        return b"{}"


@pytest.fixture(autouse=True)
def stripe_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stripe keys set, so the webhook takes deliveries."""
    monkeypatch.setattr(payment_routes.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(payment_routes.settings, "stripe_webhook_secret", "whsec_x")


@pytest.fixture
def written(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict[str, Any]]]:
    """The activity log entries and the pushes the notifications write."""
    calls: dict[str, list[dict[str, Any]]] = {"log": [], "push": []}

    async def dispatch(**kwargs: Any) -> None:
        calls["push"].append(kwargs)

    monkeypatch.setattr(
        notification_module.activity_log_service, "record", lambda **kwargs: calls["log"].append(kwargs)
    )
    monkeypatch.setattr(notification_service, "_dispatch", dispatch)
    return calls


def _deliver(db: Session, monkeypatch: pytest.MonkeyPatch, invoice: dict[str, Any]) -> dict[str, str]:
    """Deliver an ``invoice.payment_failed`` event about this invoice to the Stripe webhook."""
    event = {"type": "invoice.payment_failed", "data": {"object": invoice}}
    monkeypatch.setattr(stripe_payment_module, "get_stripe_service", lambda: _VerifiedStripe(event))
    return asyncio.run(payment_routes.stripe_webhook(_WebhookDelivery(), db, stripe_signature="t=1,v1=signature"))


def _invoice(invoice_id: str, stripe_subscription_id: str) -> dict[str, Any]:
    """An invoice of a subscription as the 2025-03-31 Stripe API renders it: the subscription under ``parent``."""
    return {
        "id": invoice_id,
        "object": "invoice",
        "parent": {"type": "subscription_details", "subscription_details": {"subscription": stripe_subscription_id}},
    }


def _subscription(db: Session, status: str) -> AiAssistantSubscription:
    """The Stripe subscription ``sub_garage`` of Garage Martin's receptionist, in this status."""
    prospect = ProspectDB(name="Garage Martin", category="Garage", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    subscription = AiAssistantSubscription(
        user_id=7,
        prospect_id=prospect.id,
        ai_assistant_id=3,
        interval="month",
        amount_cents=7900,
        status=status,
        stripe_subscription_id="sub_garage",
    )
    db.add(subscription)
    db.commit()
    return subscription


def test_a_refused_payment_puts_the_subscription_past_due_and_tells_the_operator_once(
    db: Session, monkeypatch: pytest.MonkeyPatch, written: dict[str, list[dict[str, Any]]]
) -> None:
    subscription = _subscription(db, AiAssistantSubscriptionStatus.ACTIVE.value)

    first = _deliver(db, monkeypatch, _invoice("in_october", "sub_garage"))
    replay = _deliver(db, monkeypatch, _invoice("in_october", "sub_garage"))

    db.refresh(subscription)
    assert subscription.status == AiAssistantSubscriptionStatus.PAST_DUE.value
    assert (first["status"], replay["status"]) == ("success", "ignored")
    [entry] = written["log"]
    assert (entry["action"], entry["status"]) == ("assistant_payment_failed", "warning")
    assert entry["detail"] == "Facture Stripe in_october"
    [push] = written["push"]
    assert push["body"] == "🤖 Assistant IA · Paiement refusé : Garage Martin (abonnement réceptionniste)"


def test_each_refused_invoice_is_told_once(
    db: Session, monkeypatch: pytest.MonkeyPatch, written: dict[str, list[dict[str, Any]]]
) -> None:
    _subscription(db, AiAssistantSubscriptionStatus.ACTIVE.value)

    _deliver(db, monkeypatch, _invoice("in_october", "sub_garage"))
    # Stripe's own retry of the October invoice fails too, then the November one.
    _deliver(db, monkeypatch, _invoice("in_october", "sub_garage"))
    _deliver(db, monkeypatch, _invoice("in_november", "sub_garage"))

    assert [entry["detail"] for entry in written["log"]] == ["Facture Stripe in_october", "Facture Stripe in_november"]
    assert len(written["push"]) == 2


def test_an_invoice_of_a_subscription_we_do_not_know_changes_nothing(
    db: Session, monkeypatch: pytest.MonkeyPatch, written: dict[str, list[dict[str, Any]]]
) -> None:
    subscription = _subscription(db, AiAssistantSubscriptionStatus.ACTIVE.value)
    website_invoice = {"id": "in_website", "object": "invoice", "parent": None}

    unknown = _deliver(db, monkeypatch, _invoice("in_other", "sub_other"))
    without_subscription = _deliver(db, monkeypatch, website_invoice)

    db.refresh(subscription)
    assert (subscription.status, subscription.payment_failed_invoice_id) == ("active", None)
    assert (unknown["status"], without_subscription["status"]) == ("ignored", "ignored")
    assert written == {"log": [], "push": []}


def test_a_canceled_subscription_stays_as_it_is(
    db: Session, monkeypatch: pytest.MonkeyPatch, written: dict[str, list[dict[str, Any]]]
) -> None:
    subscription = _subscription(db, AiAssistantSubscriptionStatus.CANCELED.value)

    _deliver(db, monkeypatch, _invoice("in_october", "sub_garage"))

    db.refresh(subscription)
    assert (subscription.status, subscription.payment_failed_invoice_id) == ("canceled", None)
    assert written == {"log": [], "push": []}


def test_an_invoice_from_an_older_stripe_api_names_its_subscription_on_itself(
    db: Session, monkeypatch: pytest.MonkeyPatch, written: dict[str, list[dict[str, Any]]]
) -> None:
    subscription = _subscription(db, AiAssistantSubscriptionStatus.ACTIVE.value)

    _deliver(db, monkeypatch, {"id": "in_october", "object": "invoice", "subscription": "sub_garage"})

    db.refresh(subscription)
    assert subscription.status == AiAssistantSubscriptionStatus.PAST_DUE.value
    assert len(written["push"]) == 1


def test_the_migration_adds_the_invoice_column_once(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE ai_assistant_subscriptions (id INTEGER PRIMARY KEY, status VARCHAR(32))"))
        conn.commit()
    monkeypatch.setattr(payment_failed_migration, "engine", engine)

    payment_failed_migration.run_migration()
    payment_failed_migration.run_migration()

    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistant_subscriptions")}
    assert "payment_failed_invoice_id" in columns
