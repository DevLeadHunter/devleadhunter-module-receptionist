"""AI-assistant subscription price per user — the CURRENT price for new subscriptions.

The assistant sells at 79 €/mois by default (79-99 € advised); the annual plan offers 2 months
(→ 790 €/an). Both are configurable per user (mirroring :class:`services.pricing_service.PricingService`
for the website), stored on the module's own ``ai_assistant_owner_settings`` row.

⚠️ Grandfathering: this service returns the price a NEW subscription should use. An existing
subscription keeps the price it was created with, stored on its own row — never re-read from here.
So raising the configured price only affects future subscribers; current ones stay on their price.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from core.clock import naive_utc_now
from devleadhunter_receptionist.models.ai_assistant_owner_settings import AiAssistantOwnerSettings
from services.pricing_service import PricingService

# Defaults, used when a user has not set their own.
DEFAULT_MONTHLY_PRICE_CENTS = 7900  # 79 €
DEFAULT_ANNUAL_FREE_MONTHS = 2  # → 790 €/an


class AssistantPricingService:
    """Resolve and format the assistant subscription price a user charges."""

    @staticmethod
    def monthly_price_cents(db: Session, user_id: int) -> int:
        """
        Return the user's configured assistant monthly price, in cents.

        Args:
            db: Active database session.
            user_id: Owner of the price.

        Returns:
            The stored monthly price, or ``DEFAULT_MONTHLY_PRICE_CENTS`` (79 €) when unset.
        """
        owner_settings: AiAssistantOwnerSettings | None = db.get(AiAssistantOwnerSettings, user_id)
        if owner_settings is None:
            return DEFAULT_MONTHLY_PRICE_CENTS
        return owner_settings.monthly_price_cents

    @staticmethod
    def annual_free_months(db: Session, user_id: int) -> int:
        """
        Return how many months are offered on the annual plan (0-11).

        Args:
            db: Active database session.
            user_id: Owner of the price.

        Returns:
            The stored free-month count, or ``DEFAULT_ANNUAL_FREE_MONTHS`` (2) when unset.
        """
        owner_settings: AiAssistantOwnerSettings | None = db.get(AiAssistantOwnerSettings, user_id)
        if owner_settings is None:
            return DEFAULT_ANNUAL_FREE_MONTHS
        return max(0, min(11, owner_settings.annual_free_months))

    @staticmethod
    def annual_price_cents(db: Session, user_id: int) -> int:
        """
        Return the annual price: ``monthly × (12 - free_months)`` (79 € × 10 = 790 €).

        Args:
            db: Active database session.
            user_id: Owner of the price.

        Returns:
            The annual price in cents (always at least one month billed).
        """
        monthly = AssistantPricingService.monthly_price_cents(db, user_id)
        billed_months = max(1, 12 - AssistantPricingService.annual_free_months(db, user_id))
        return monthly * billed_months

    @staticmethod
    def save_prices(
        db: Session, user_id: int, *, monthly_price_cents: int | None, annual_free_months: int | None
    ) -> AiAssistantOwnerSettings:
        """
        Change the price the user charges new subscribers (a field left None keeps its value).

        Args:
            db: Active database session.
            user_id: Owner of the price.
            monthly_price_cents: The new monthly price in cents, or None.
            annual_free_months: The new number of months offered on the annual plan (0-11), or None.

        Returns:
            The stored settings.
        """
        owner_settings: AiAssistantOwnerSettings | None = db.get(AiAssistantOwnerSettings, user_id)
        if owner_settings is None:
            owner_settings = AiAssistantOwnerSettings(
                user_id=user_id,
                monthly_price_cents=DEFAULT_MONTHLY_PRICE_CENTS,
                annual_free_months=DEFAULT_ANNUAL_FREE_MONTHS,
            )
            db.add(owner_settings)
        if monthly_price_cents is not None:
            owner_settings.monthly_price_cents = monthly_price_cents
        if annual_free_months is not None:
            owner_settings.annual_free_months = max(0, min(11, annual_free_months))
        owner_settings.updated_at = naive_utc_now()
        db.commit()
        return owner_settings

    @staticmethod
    def format_price(cents: int) -> str:
        """Render a cents amount as a French euro string ("79 €", "790 €") — shared with the site."""
        return PricingService.format_price(cents)


assistant_pricing_service = AssistantPricingService()
