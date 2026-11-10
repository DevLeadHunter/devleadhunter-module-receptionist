"""
Add the « Pour démarrer » columns of ``ai_assistants``: the sale date, the widget's sighting on the business's site,
the Google-profile step, and the two start reminders. Sold assistants get their sale date backfilled.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine

_COLUMNS: tuple[tuple[str, str], ...] = (
    ("delivered_at", "DATETIME NULL"),
    ("installed_at", "DATETIME NULL"),
    ("installed_host", "VARCHAR(255) NULL"),
    ("google_profile_linked_at", "DATETIME NULL"),
    ("start_reminder_j3_sent_at", "DATETIME NULL"),
    ("start_reminder_j14_sent_at", "DATETIME NULL"),
)


def run_migration() -> None:
    """Add the missing columns (re-runnable) and date the assistants already sold."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    with engine.connect() as conn:
        for name, definition in _COLUMNS:
            if name not in columns:
                conn.execute(text(f"ALTER TABLE ai_assistants ADD COLUMN {name} {definition}"))
        conn.execute(
            text(
                "UPDATE ai_assistants SET delivered_at = COALESCE(updated_at, created_at) "
                "WHERE status = 'delivered' AND delivered_at IS NULL"
            )
        )
        conn.commit()


if __name__ == "__main__":
    run_migration()
