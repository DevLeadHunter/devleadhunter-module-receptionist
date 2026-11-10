"""Add the owner-alert settings to ``ai_assistants``, their tracking to ``ai_assistant_requests``, and
``sms_messages.kind`` so the owner alerts (service SMS) stay out of the prospecting cap and recap."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine

# Every column is nullable: NULL keeps the default behaviour, so existing rows need no backfill.
_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "ai_assistants": (
        ("alert_phone_e164", "VARCHAR(20) NULL"),
        ("alert_sms_enabled", "BOOLEAN NULL"),
        ("alert_email_enabled", "BOOLEAN NULL"),
        ("alert_sms_types", "JSON NULL"),
        ("alert_quiet_start_hour", "INT NULL"),
        ("alert_quiet_end_hour", "INT NULL"),
    ),
    "ai_assistant_requests": (
        ("owner_alerted_at", "DATETIME NULL"),
        ("sms_due_at", "DATETIME NULL"),
        ("sms_sent_at", "DATETIME NULL"),
        ("reminder_sent_at", "DATETIME NULL"),
        ("stale_notified_at", "DATETIME NULL"),
    ),
    "sms_messages": (("kind", "VARCHAR(16) NULL"),),
}


def run_migration() -> None:
    """Add each missing column (re-runnable)."""
    inspector = inspect(engine)
    with engine.connect() as conn:
        for table, columns in _COLUMNS.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
