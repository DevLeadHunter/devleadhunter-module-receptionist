"""The receptionist price the user charges new subscribers (Paramètres → Réceptionniste IA)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from devleadhunter_receptionist.schemas.ai_assistant_pricing import AssistantPricingResponse, AssistantPricingUpdate
from devleadhunter_receptionist.services.assistant_pricing_service import AssistantPricingService
from models.user import User
from services.auth_service import get_current_active_user

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistants"])


@router.get("/pricing", response_model=AssistantPricingResponse)
async def get_assistant_pricing(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AssistantPricingResponse:
    """The price new receptionist subscribers pay; existing subscriptions keep the price they were sold at."""
    return AssistantPricingResponse(
        monthly_price_cents=AssistantPricingService.monthly_price_cents(db, current_user.id),
        annual_free_months=AssistantPricingService.annual_free_months(db, current_user.id),
    )


@router.put("/pricing", response_model=AssistantPricingResponse)
async def update_assistant_pricing(
    payload: AssistantPricingUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AssistantPricingResponse:
    """Change the price new receptionist subscribers will pay."""
    AssistantPricingService.save_prices(
        db,
        current_user.id,
        monthly_price_cents=payload.monthly_price_cents,
        annual_free_months=payload.annual_free_months,
    )
    return AssistantPricingResponse(
        monthly_price_cents=AssistantPricingService.monthly_price_cents(db, current_user.id),
        annual_free_months=AssistantPricingService.annual_free_months(db, current_user.id),
    )
