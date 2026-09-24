"""Add ``ai_assistant_requests.appointment_slots_json``: the half-days a visitor wishes an appointment in."""

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
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistant_requests")}
    if "appointment_slots_json" in columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_assistant_requests ADD COLUMN appointment_slots_json JSON NULL"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
