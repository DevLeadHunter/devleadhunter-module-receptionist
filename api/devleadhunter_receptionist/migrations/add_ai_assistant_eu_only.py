"""Add ``ai_assistants.eu_only``: the assistant's model calls stay with Mistral, without Groq fallback."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine


def run_migration() -> None:
    """Add the nullable column if it is missing (NULL reads as False; re-runnable)."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    if "eu_only" in columns:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_assistants ADD COLUMN eu_only BOOLEAN NULL"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
