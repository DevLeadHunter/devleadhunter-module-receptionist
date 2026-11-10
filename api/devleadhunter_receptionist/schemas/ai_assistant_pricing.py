"""Contracts of the receptionist price (Paramètres → Réceptionniste IA)."""

from pydantic import BaseModel, Field


class AssistantPricingResponse(BaseModel):
    """The user's current receptionist price."""

    monthly_price_cents: int = Field(description="Monthly subscription price in cents (default 79 €)")
    annual_free_months: int = Field(description="Months offered on the annual plan (default 2 → 790 €/an)")


class AssistantPricingUpdate(BaseModel):
    """A new receptionist price; a field left out keeps its value."""

    monthly_price_cents: int | None = Field(default=None, ge=0, description="Monthly price in cents")
    annual_free_months: int | None = Field(default=None, ge=0, le=11, description="Months offered on the annual plan")
