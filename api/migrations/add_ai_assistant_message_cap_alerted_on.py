"""Add ``ai_assistants.message_cap_alerted_on``: the business day its operator was told the daily cap was reached."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine


def run_migration() -> None:
    """Add the nullable DATE column if it is missing (re-runnable)."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    if "message_cap_alerted_on" in columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_assistants ADD COLUMN message_cap_alerted_on DATE NULL"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
