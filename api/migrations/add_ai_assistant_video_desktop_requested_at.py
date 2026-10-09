"""Add ``ai_assistants.video_desktop_requested_at``: the receptionist's video waits for the owner's desktop app."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine


def run_migration() -> None:
    """Add the column if it is missing: every receptionist starts without a request (re-runnable)."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    if "video_desktop_requested_at" in columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_assistants ADD COLUMN video_desktop_requested_at DATETIME NULL"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
