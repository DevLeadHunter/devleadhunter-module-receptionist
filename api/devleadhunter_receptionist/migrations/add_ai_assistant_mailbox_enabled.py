"""Add ``ai_assistants.mailbox_enabled``: the operator switched on the Gmail mailbox for this receptionist."""

from __future__ import annotations

from sqlalchemy import inspect, text

from core.database import engine


def run_migration() -> None:
    """Add the column, off for every existing receptionist, if it is missing (re-runnable)."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    if "mailbox_enabled" in columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_assistants ADD COLUMN mailbox_enabled BOOLEAN NOT NULL DEFAULT 0"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
