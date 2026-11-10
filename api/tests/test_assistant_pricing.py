"""Assistant subscription pricing: monthly/annual resolution, defaults, formatting."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.orm import Session

from devleadhunter_receptionist.models.ai_assistant_owner_settings import AiAssistantOwnerSettings
from devleadhunter_receptionist.services.assistant_pricing_service import AssistantPricingService


class _FakeDB:
    def __init__(self, user: SimpleNamespace | None) -> None:
        self._user = user

    def get(self, model: object, pk: object) -> SimpleNamespace | None:
        return self._user


def test_defaults_when_user_or_value_missing() -> None:
    assert AssistantPricingService.monthly_price_cents(_FakeDB(None), 1) == 7900
    assert AssistantPricingService.annual_free_months(_FakeDB(None), 1) == 2
    assert AssistantPricingService.annual_price_cents(_FakeDB(None), 1) == 79000  # 7900 × (12-2)


def test_configured_price_drives_monthly_and_annual() -> None:
    user = SimpleNamespace(monthly_price_cents=3900, annual_free_months=2)
    db = _FakeDB(user)
    assert AssistantPricingService.monthly_price_cents(db, 1) == 3900
    assert AssistantPricingService.annual_price_cents(db, 1) == 39000  # 3900 × 10


def test_annual_free_months_changes_annual_total() -> None:
    user = SimpleNamespace(monthly_price_cents=2900, annual_free_months=3)
    assert AssistantPricingService.annual_price_cents(_FakeDB(user), 1) == 26100  # 2900 × (12-3)


def test_free_months_clamped_and_annual_bills_at_least_one_month() -> None:
    user = SimpleNamespace(monthly_price_cents=2900, annual_free_months=15)
    db = _FakeDB(user)
    assert AssistantPricingService.annual_free_months(db, 1) == 11  # clamped to 0..11
    assert AssistantPricingService.annual_price_cents(db, 1) == 2900  # 12-11 = 1 month billed


def test_format_price() -> None:
    assert AssistantPricingService.format_price(2900) == "29 €"
    assert AssistantPricingService.format_price(29000) == "290 €"
    assert AssistantPricingService.format_price(2990) == "29,90 €"


def test_the_price_is_saved_on_the_module_row_and_a_missing_field_keeps_its_value(db: Session) -> None:
    AssistantPricingService.save_prices(db, 4, monthly_price_cents=5900, annual_free_months=None)
    AssistantPricingService.save_prices(db, 4, monthly_price_cents=None, annual_free_months=15)

    stored = db.get(AiAssistantOwnerSettings, 4)
    assert stored is not None and (stored.monthly_price_cents, stored.annual_free_months) == (5900, 11)
    assert AssistantPricingService.monthly_price_cents(db, 4) == 5900
    assert AssistantPricingService.annual_price_cents(db, 4) == 5900
