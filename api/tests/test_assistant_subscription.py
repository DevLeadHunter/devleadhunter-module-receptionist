"""Assistant subscription service: price lock (grandfathering) + webhook status sync."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from enums.assistant_subscription_status import AssistantSubscriptionStatus
from models.ai_assistant_subscription import AiAssistantSubscription
from services import assistant_subscription_service as sub_module
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

    service.activate_from_session(
        db,
        {
            "metadata": {"assistant_subscription_id": str(row.id)},
            "subscription": "sub_123",
            "customer": "cus_123",
            "customer_details": {"email": "client@shop.fr", "name": "Le Client"},
        },
    )
    db.refresh(row)
    assert row.status == AssistantSubscriptionStatus.ACTIVE.value
    assert row.stripe_subscription_id == "sub_123"
    assert row.client_email == "client@shop.fr"


def test_update_from_stripe_subscription_syncs_status_and_cancel(db: Session) -> None:
    service = AssistantSubscriptionService()
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

    service.update_from_stripe_subscription(
        db, {"id": "sub_9", "status": "canceled", "current_period_end": 1_800_000_000}
    )
    db.refresh(row)
    assert row.status == AssistantSubscriptionStatus.CANCELED.value
    assert row.canceled_at is not None
    assert row.current_period_end is not None


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
