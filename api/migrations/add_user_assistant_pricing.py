"""Add the AI-assistant subscription pricing columns to users.

``assistant_monthly_price_cents`` defaults to 2900 (29 € launch) and
``assistant_annual_free_months`` to 2 (→ 290 €/an). ``ADD COLUMN`` with a DEFAULT
sets every existing row in place, so no separate backfill pass is needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine


def _column_exists(conn, column_name: str) -> bool:
    result = conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = :column_name
            """
        ),
        {"column_name": column_name},
    )
    return bool(result.scalar())


def run_migration() -> None:
    with engine.connect() as conn:
        if not _column_exists(conn, "assistant_monthly_price_cents"):
            conn.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD COLUMN assistant_monthly_price_cents INT NOT NULL DEFAULT 2900
                    """
                )
            )
        if not _column_exists(conn, "assistant_annual_free_months"):
            conn.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD COLUMN assistant_annual_free_months INT NOT NULL DEFAULT 2
                    """
                )
            )
        conn.commit()


if __name__ == "__main__":
    run_migration()
    print("users assistant pricing columns ensured.")
