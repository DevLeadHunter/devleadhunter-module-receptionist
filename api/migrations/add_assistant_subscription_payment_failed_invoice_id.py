"""Add ``ai_assistant_subscriptions.payment_failed_invoice_id``: the last invoice whose failed payment was notified."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine


def run_migration() -> None:
    """Add the nullable column if it is missing (re-runnable)."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistant_subscriptions")}
    if "payment_failed_invoice_id" in columns:
        return
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE ai_assistant_subscriptions ADD COLUMN payment_failed_invoice_id VARCHAR(255) NULL")
        )
        conn.commit()


if __name__ == "__main__":
    run_migration()
