"""Add ``ai_assistant_subscriptions.activated_at``: when the client paid, the start of the service."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine


def run_migration() -> None:
    """Add the nullable column if it is missing (NULL: activated before it existed; re-runnable)."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistant_subscriptions")}
    if "activated_at" in columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_assistant_subscriptions ADD COLUMN activated_at DATETIME NULL"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
