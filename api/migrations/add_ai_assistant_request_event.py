"""Add ``ai_assistant_requests.event_json``: the details of an event request (date, place, guests, budget)."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine


def run_migration() -> None:
    """Add the nullable JSON column if it is missing (re-runnable)."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistant_requests")}
    if "event_json" in columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_assistant_requests ADD COLUMN event_json JSON NULL"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
