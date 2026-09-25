"""Move the AI-assistant default price from 29 € to 79 € a month.

The accounts still on the old default (2900) move to 7900; an account whose owner set another price
keeps it. Existing subscriptions are untouched: each keeps the price stored on its own row. On
MySQL / MariaDB the column default follows, so new accounts start at 79 €. Re-runnable.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine

_OLD_DEFAULT_CENTS = 2900
_NEW_DEFAULT_CENTS = 7900


def run_migration() -> None:
    """Raise the accounts still on the old default, then the column default (MySQL / MariaDB)."""
    with engine.connect() as conn:
        moved = conn.execute(
            text("SELECT id FROM users WHERE assistant_monthly_price_cents = :old"), {"old": _OLD_DEFAULT_CENTS}
        ).all()
        conn.execute(
            text("UPDATE users SET assistant_monthly_price_cents = :new WHERE assistant_monthly_price_cents = :old"),
            {"new": _NEW_DEFAULT_CENTS, "old": _OLD_DEFAULT_CENTS},
        )
        # Traceability (ids only: the deploy log is not the place for addresses): an owner who had chosen 29 €
        # on purpose can be set back by hand.
        for (user_id,) in moved:
            print(f"[OK] Assistant price 29 € → 79 € for user {user_id}")
        if engine.dialect.name in {"mysql", "mariadb"}:
            conn.execute(
                text(f"ALTER TABLE users ALTER assistant_monthly_price_cents SET DEFAULT {_NEW_DEFAULT_CENTS}")
            )
        conn.commit()


if __name__ == "__main__":
    run_migration()
