"""
Add the receptionist's own portrait to ``ai_assistants``: its storage key, whether it is shown, whether it has
transparent areas, and the colour of the disc behind a cut-out portrait.
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
    ("avatar_key", "VARCHAR(255) NULL"),
    ("avatar_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
    ("avatar_is_transparent", "BOOLEAN NULL"),
    ("avatar_background", "VARCHAR(16) NULL"),
)


def run_migration() -> None:
    """Add the missing columns (re-runnable): every receptionist keeps its casting face and the accent's tint."""
    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    with engine.connect() as conn:
        for name, definition in _COLUMNS:
            if name not in columns:
                conn.execute(text(f"ALTER TABLE ai_assistants ADD COLUMN {name} {definition}"))
        conn.commit()


if __name__ == "__main__":
    run_migration()
