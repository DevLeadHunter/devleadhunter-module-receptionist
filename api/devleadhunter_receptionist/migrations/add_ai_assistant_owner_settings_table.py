"""Create ai_assistant_owner_settings and copy each user's receptionist price into it.

The price used to live on ``users`` (``assistant_monthly_price_cents``, ``assistant_annual_free_months``); the core no
longer knows it. Those columns are left in place (with their server defaults) and copied once: a user who already
has a row keeps it. Re-runnable.
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from core.clock import naive_utc_now
from core.database import engine
from devleadhunter_receptionist.models.ai_assistant_owner_settings import AiAssistantOwnerSettings

_LEGACY_COLUMNS: frozenset[str] = frozenset({"assistant_monthly_price_cents", "assistant_annual_free_months"})


def run_migration() -> None:
    """Create the table if needed, then copy the prices still only stored on ``users``."""
    AiAssistantOwnerSettings.__table__.create(engine, checkfirst=True)
    user_columns: set[str] = {column["name"] for column in inspect(engine).get_columns("users")}
    if not user_columns >= _LEGACY_COLUMNS:
        return
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, assistant_monthly_price_cents, assistant_annual_free_months FROM users "
                "WHERE id NOT IN (SELECT user_id FROM ai_assistant_owner_settings)"
            )
        ).all()
        for user_id, monthly_price_cents, annual_free_months in rows:
            conn.execute(
                text(
                    "INSERT INTO ai_assistant_owner_settings "
                    "(user_id, monthly_price_cents, annual_free_months, updated_at) "
                    "VALUES (:user_id, :monthly, :free_months, :updated_at)"
                ),
                {
                    "user_id": user_id,
                    "monthly": monthly_price_cents if monthly_price_cents is not None else 7900,
                    "free_months": annual_free_months if annual_free_months is not None else 2,
                    "updated_at": naive_utc_now(),
                },
            )
