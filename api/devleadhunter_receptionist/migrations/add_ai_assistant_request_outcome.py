"""Add ``ai_assistant_requests.outcome`` / ``outcome_at``: a client won or lost, as the owner marks it."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine

_COLUMNS: tuple[tuple[str, str], ...] = (("outcome", "VARCHAR(8) NULL"), ("outcome_at", "DATETIME NULL"))


def run_migration() -> None:
    """Add the nullable columns if they are missing (re-runnable)."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistant_requests")}
    with engine.connect() as conn:
        for name, definition in _COLUMNS:
            if name not in columns:
                conn.execute(text(f"ALTER TABLE ai_assistant_requests ADD COLUMN {name} {definition}"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
