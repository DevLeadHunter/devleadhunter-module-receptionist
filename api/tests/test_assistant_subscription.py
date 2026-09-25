"""Assistant subscription service: price lock (grandfathering) + webhook status sync."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from enums.ai_assistant_status import AiAssistantStatus
from enums.assistant_subscription_status import AssistantSubscriptionStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_subscription import AiAssistantSubscription
from services import assistant_subscription_service as sub_module
from services.ai_assistant.assistant_service import ai_assistant_service
from services.assistant_subscription_service import AssistantSubscriptionService


def _import_all_models() -> None:
    """Import every model module so SQLAlchemy can configure the whole mapper registry."""
    import importlib
    import pkgutil

    import models

    for module in pkgutil.iter_modules(models.__path__):
        importlib.import_module(f"models.{module.name}")


@pytest.fixture
def db() -> Iterator[Session]:
    _import_all_models()
    engine = create_engine("sqlite:///:memory:")
    AiAssistantSubscription.__table__.create(engine)
    AiAssistant.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _assistant() -> SimpleNamespace:
    return SimpleNamespace(id=7, prospect_id=42, business_name="Barbershop 63")


def _stub_stripe(service: AssistantSubscriptionService, monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(id="cs_test_123", url="https://checkout.stripe.test/cs_test_123")
    monkeypatch.setattr(service._stripe.checkout.Session, "create", lambda **kwargs: session, raising=False)
    monkeypatch.setattr(sub_module.settings, "stripe_secret_key", "sk_test_x", raising=False)


def test_checkout_locks_the_monthly_price_on_the_row(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    service = AssistantSubscriptionService()
    _stub_stripe(service, monkeypatch)
    monkeypatch.setattr(sub_module.AssistantPricingService, "monthly_price_cents", staticmethod(lambda _db, _uid: 2900))

    url = service.create_checkout_session(
        db, user_id=1, assistant=_assistant(), interval="month", success_url="s", cancel_url="c"
    )

    assert url == "https://checkout.stripe.test/cs_test_123"
    row = db.query(AiAssistantSubscription).one()
    assert row.amount_cents == 2900
    assert row.interval == "month"
    assert row.status == AssistantSubscriptionStatus.INCOMPLETE.value
    assert row.stripe_checkout_session_id == "cs_test_123"


def test_checkout_uses_annual_price_for_year_interval(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    service = AssistantSubscriptionService()
    _stub_stripe(service, monkeypatch)
    monkeypatch.setattr(sub_module.AssistantPricingService, "annual_price_cents", staticmethod(lambda _db, _uid: 29000))

    service.create_checkout_session(
        db, user_id=1, assistant=_assistant(), interval="year", success_url="s", cancel_url="c"
    )
    row = db.query(AiAssistantSubscription).one()
    assert row.amount_cents == 29000
    assert row.interval == "year"


def test_grandfathering_existing_row_keeps_its_price_when_config_rises(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = AssistantSubscriptionService()
    _stub_stripe(service, monkeypatch)

    # First client subscribes at the 29 € launch price.
    monkeypatch.setattr(sub_module.AssistantPricingService, "monthly_price_cents", staticmethod(lambda _db, _uid: 2900))
    service.create_checkout_session(
        db, user_id=1, assistant=_assistant(), interval="month", success_url="s", cancel_url="c"
    )
    # The owner later raises the configured price to 39 €.
    monkeypatch.setattr(sub_module.AssistantPricingService, "monthly_price_cents", staticmethod(lambda _db, _uid: 3900))

    existing = db.query(AiAssistantSubscription).one()
    assert existing.amount_cents == 2900  # locked — the rise never touches an existing subscriber


def test_activate_from_session_marks_active_and_stores_ids(db: Session) -> None:
    service = AssistantSubscriptionService()
    row = AiAssistantSubscription(
        user_id=1, ai_assistant_id=7, interval="month", amount_cents=2900, status="incomplete"
    )
    db.add(row)
    db.commit()

    session_obj = {
        "metadata": {"assistant_subscription_id": str(row.id)},
        "subscription": "sub_123",
        "customer": "cus_123",
        "customer_details": {"email": "client@shop.fr", "name": "Le Client"},
    }
    fresh = service.activate_from_session(db, session_obj)
    db.refresh(row)
    assert row.status == AssistantSubscriptionStatus.ACTIVE.value
    assert row.stripe_subscription_id == "sub_123"
    assert row.client_email == "client@shop.fr"
    assert fresh is not None and fresh.id == row.id  # returned on fresh activation → the seller is notified
    assert service.activate_from_session(db, session_obj) is None  # idempotent retry → no second notification


def test_update_from_stripe_subscription_syncs_status_and_cancel(db: Session) -> None:
    service = AssistantSubscriptionService()
    assistant = AiAssistant(
        id=7, user_id=1, slug="barbershop-63", business_name="Barbershop 63", status=AiAssistantStatus.DELIVERED.value
    )
    db.add(assistant)
    row = AiAssistantSubscription(
        user_id=1,
        ai_assistant_id=7,
        interval="month",
        amount_cents=2900,
        status="active",
        stripe_subscription_id="sub_9",
    )
    db.add(row)
    db.commit()

    # Since the Basil API the period end sits on each subscription item, not on the subscription.
    service.update_from_stripe_subscription(
        db, {"id": "sub_9", "status": "canceled", "items": {"data": [{"current_period_end": 1_800_000_000}]}}
    )
    db.refresh(row)
    db.refresh(assistant)
    assert row.status == AssistantSubscriptionStatus.CANCELED.value
    assert row.canceled_at is not None
    assert row.current_period_end == datetime(2027, 1, 15, 8, 0)
    # The service ends with the subscription: the assistant is retired.
    assert assistant.status == AiAssistantStatus.EXPIRED.value


def test_activation_marks_the_sold_assistant_delivered(db: Session) -> None:
    service = AssistantSubscriptionService()
    assistant = AiAssistant(
        id=7, user_id=1, slug="barbershop-63", business_name="Barbershop 63", status=AiAssistantStatus.ACTIVE.value
    )
    db.add(assistant)
    row = AiAssistantSubscription(
        user_id=1, ai_assistant_id=7, interval="month", amount_cents=2900, status="incomplete"
    )
    db.add(row)
    db.commit()

    service.activate_from_session(db, {"metadata": {"assistant_subscription_id": str(row.id)}, "subscription": "sub_1"})
    db.refresh(assistant)
    assert assistant.status == AiAssistantStatus.DELIVERED.value  # protected from the demo TTL
    assert ai_assistant_service.get_public_by_slug(db, "barbershop-63") is not None  # the widget keeps answering


def test_is_active_for_assistant(db: Session) -> None:
    service = AssistantSubscriptionService()
    db.add(AiAssistantSubscription(user_id=1, ai_assistant_id=7, interval="month", amount_cents=2900, status="active"))
    db.add(
        AiAssistantSubscription(user_id=1, ai_assistant_id=8, interval="month", amount_cents=2900, status="canceled")
    )
    db.commit()
    assert service.is_active_for_assistant(db, 7) is True
    assert service.is_active_for_assistant(db, 8) is False
    assert service.is_active_for_assistant(db, 99) is False

    by_id = service.active_by_assistant_ids(db, [7, 8, 99])
    assert set(by_id) == {7}  # only the active one, keyed by assistant id
    assert by_id[7].amount_cents == 2900
    assert service.active_by_assistant_ids(db, []) == {}


def test_stats_normalizes_annual_to_monthly_mrr(db: Session) -> None:
    service = AssistantSubscriptionService()
    db.add(AiAssistantSubscription(user_id=1, ai_assistant_id=1, interval="month", amount_cents=2900, status="active"))
    db.add(AiAssistantSubscription(user_id=1, ai_assistant_id=2, interval="year", amount_cents=29000, status="active"))
    db.add(
        AiAssistantSubscription(user_id=1, ai_assistant_id=3, interval="month", amount_cents=2900, status="canceled")
    )
    db.commit()

    active_count, mrr_cents = service.stats_for_user(db, 1)
    assert active_count == 2  # the canceled one is excluded
    assert mrr_cents == 2900 + 29000 // 12  # annual normalised to its monthly share


def test_cancel_incomplete_row_closes_locally_without_stripe(db: Session) -> None:
    service = AssistantSubscriptionService()
    row = AiAssistantSubscription(
        user_id=1, ai_assistant_id=1, interval="month", amount_cents=2900, status="incomplete"
    )
    db.add(row)
    db.commit()

    service.cancel(db, row)  # no stripe_subscription_id → no Stripe call
    db.refresh(row)
    assert row.status == AssistantSubscriptionStatus.CANCELED.value
    assert row.canceled_at is not None


def test_cancel_active_calls_stripe(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    service = AssistantSubscriptionService()
    monkeypatch.setattr(sub_module.settings, "stripe_secret_key", "sk_test_x", raising=False)
    cancelled: list[str] = []
    monkeypatch.setattr(service._stripe.Subscription, "cancel", lambda sub_id: cancelled.append(sub_id), raising=False)
    row = AiAssistantSubscription(
        user_id=1,
        ai_assistant_id=1,
        interval="month",
        amount_cents=2900,
        status="active",
        stripe_subscription_id="sub_9",
    )
    db.add(row)
    db.commit()

    service.cancel(db, row)
    db.refresh(row)
    assert cancelled == ["sub_9"]  # Stripe was told to cancel
    assert row.status == AssistantSubscriptionStatus.CANCELED.value


def test_list_for_user_returns_rows_with_names(db: Session) -> None:
    service = AssistantSubscriptionService()
    db.add(
        AiAssistant(id=1, user_id=1, slug="s1", business_name="Barbershop 63", status=AiAssistantStatus.DELIVERED.value)
    )
    db.add(AiAssistantSubscription(user_id=1, ai_assistant_id=1, interval="month", amount_cents=2900, status="active"))
    db.commit()

    rows = service.list_for_user(db, 1)
    assert len(rows) == 1
    subscription, business_name, _assistant_name = rows[0]
    assert subscription.amount_cents == 2900
    assert business_name == "Barbershop 63"


def test_subscription_link_is_permanent_and_targets_the_public_subscribe_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sub_module.settings, "api_base_url", "https://api.devleadhunter.test/", raising=False)
    link = AssistantSubscriptionService.subscription_link(SimpleNamespace(slug="barbershop-63"), "year")
    assert link == "https://api.devleadhunter.test/api/v1/ai-assistants/public/barbershop-63/subscribe?interval=year"


def test_checkout_reuses_the_recent_unpaid_row_at_the_current_price(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = AssistantSubscriptionService()
    _stub_stripe(service, monkeypatch)
    monkeypatch.setattr(sub_module.AssistantPricingService, "monthly_price_cents", staticmethod(lambda _db, _uid: 2900))
    service.create_checkout_session(
        db, user_id=1, assistant=_assistant(), interval="month", success_url="s", cancel_url="c"
    )
    # The client clicks the permanent link again after the owner raised the price: same row, new price.
    monkeypatch.setattr(sub_module.AssistantPricingService, "monthly_price_cents", staticmethod(lambda _db, _uid: 3900))
    service.create_checkout_session(
        db, user_id=1, assistant=_assistant(), interval="month", success_url="s", cancel_url="c"
    )

    rows = db.query(AiAssistantSubscription).all()
    assert len(rows) == 1
    assert rows[0].amount_cents == 3900  # unpaid, so nothing was grandfathered yet
    assert rows[0].stripe_checkout_session_id == "cs_test_123"


def test_purge_stale_incomplete_rows_keeps_recent_and_paid_ones(db: Session) -> None:
    service = AssistantSubscriptionService()
    stale = AiAssistantSubscription(
        user_id=1, ai_assistant_id=7, interval="month", amount_cents=2900, status="incomplete"
    )
    stale.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=8)
    old_but_paid = AiAssistantSubscription(
        user_id=1, ai_assistant_id=8, interval="month", amount_cents=2900, status="active"
    )
    old_but_paid.created_at = stale.created_at
    fresh = AiAssistantSubscription(
        user_id=1, ai_assistant_id=9, interval="month", amount_cents=2900, status="incomplete"
    )
    db.add_all([stale, old_but_paid, fresh])
    db.commit()

    assert service.purge_stale_incomplete_rows(db) == 1
    remaining = {row.ai_assistant_id for row in db.query(AiAssistantSubscription).all()}
    assert remaining == {8, 9}


def _stub_refund(service: AssistantSubscriptionService, monkeypatch: pytest.MonkeyPatch, invoice: dict) -> list[dict]:
    """Stub the Stripe reads of a refund around one invoice payload and capture the Refund.create calls."""
    refunds: list[dict] = []
    monkeypatch.setattr(sub_module.settings, "stripe_secret_key", "sk_test_x", raising=False)
    monkeypatch.setattr(
        service._stripe.Subscription, "retrieve", lambda sub_id: {"latest_invoice": "in_1"}, raising=False
    )
    monkeypatch.setattr(service._stripe.Invoice, "retrieve", lambda invoice_id, **kwargs: invoice, raising=False)
    monkeypatch.setattr(service._stripe.Refund, "create", lambda **kwargs: refunds.append(kwargs), raising=False)
    return refunds


def test_refund_reads_the_payment_from_the_basil_invoice_payments(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AssistantSubscriptionService()
    basil_invoice = {"id": "in_1", "payments": {"data": [{"payment": {"payment_intent": {"id": "pi_1"}}}]}}
    refunds = _stub_refund(service, monkeypatch, basil_invoice)

    service.refund_last_payment(object(), SimpleNamespace(stripe_subscription_id="sub_1"))

    assert refunds == [{"payment_intent": "pi_1"}]


def test_refund_falls_back_to_the_invoice_charge_via_the_customer(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AssistantSubscriptionService()
    refunds = _stub_refund(service, monkeypatch, {"id": "in_1", "customer": "cus_1"})
    charges = {
        "data": [{"id": "ch_0", "invoice": "in_0", "paid": True}, {"id": "ch_1", "invoice": "in_1", "paid": True}]
    }
    monkeypatch.setattr(service._stripe.Charge, "list", lambda **kwargs: charges, raising=False)

    service.refund_last_payment(object(), SimpleNamespace(stripe_subscription_id="sub_1"))

    assert refunds == [{"charge": "ch_1"}]


def test_refund_without_any_payment_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AssistantSubscriptionService()
    _stub_refund(service, monkeypatch, {"id": "in_1", "customer": "cus_1"})
    monkeypatch.setattr(service._stripe.Charge, "list", lambda **kwargs: {"data": []}, raising=False)

    with pytest.raises(ValueError):
        service.refund_last_payment(object(), SimpleNamespace(stripe_subscription_id="sub_1"))


def test_activation_revives_an_expired_demo(db: Session) -> None:
    service = AssistantSubscriptionService()
    assistant = AiAssistant(
        id=7, user_id=1, slug="barbershop-63", business_name="Barbershop 63", status=AiAssistantStatus.EXPIRED.value
    )
    db.add(assistant)
    row = AiAssistantSubscription(
        user_id=1, ai_assistant_id=7, interval="month", amount_cents=2900, status="incomplete"
    )
    db.add(row)
    db.commit()

    service.activate_from_session(db, {"metadata": {"assistant_subscription_id": str(row.id)}, "subscription": "sub_1"})
    db.refresh(assistant)
    assert assistant.status == AiAssistantStatus.DELIVERED.value  # the paying client gets their assistant back
