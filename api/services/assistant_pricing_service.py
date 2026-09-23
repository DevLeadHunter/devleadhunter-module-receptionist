"""AI-assistant subscription price per user — the CURRENT price for new subscriptions.

Léo launches the assistant at 29 €/mois; the annual plan offers 2 months (→ 290 €/an). Both are
configurable per user (mirroring :class:`services.pricing_service.PricingService` for the website).

⚠️ Grandfathering: this service returns the price a NEW subscription should use. An existing
subscription keeps the price it was created with, stored on its own row — never re-read from here.
So raising the configured price only affects future subscribers; current ones stay on their price.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.user import User
from services.pricing_service import PricingService

# Launch defaults, used when a user has not set their own.
DEFAULT_MONTHLY_PRICE_CENTS = 2900  # 29 €
DEFAULT_ANNUAL_FREE_MONTHS = 2  # → 290 €/an


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
            The stored monthly price, or ``DEFAULT_MONTHLY_PRICE_CENTS`` (29 €) when unset.
        """
        user: User | None = db.get(User, user_id)
        if user is None or user.assistant_monthly_price_cents is None:
            return DEFAULT_MONTHLY_PRICE_CENTS
        return user.assistant_monthly_price_cents

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
        user: User | None = db.get(User, user_id)
        if user is None or user.assistant_annual_free_months is None:
            return DEFAULT_ANNUAL_FREE_MONTHS
        return max(0, min(11, user.assistant_annual_free_months))

    @staticmethod
    def annual_price_cents(db: Session, user_id: int) -> int:
        """
        Return the annual price: ``monthly × (12 - free_months)`` (29 € × 10 = 290 €).

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
    def format_price(cents: int) -> str:
        """Render a cents amount as a French euro string ("29 €", "290 €") — shared with the site."""
        return PricingService.format_price(cents)


assistant_pricing_service = AssistantPricingService()
