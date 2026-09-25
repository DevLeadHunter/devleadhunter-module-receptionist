"""Add ``ai_assistant_messages.photo_url``: the photo a visitor's turn carried, shown in the owner's journal."""

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
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistant_messages")}
    if "photo_url" in columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_assistant_messages ADD COLUMN photo_url VARCHAR(512) NULL"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
