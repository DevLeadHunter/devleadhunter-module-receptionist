"""Convert every ``ai_assistant*`` table still in a legacy charset to utf8mb4.

The conversation and message tables were created on a database whose default charset was latin1, before the
models declared utf8mb4: a visitor's emoji or non-Latin text then fails to insert and the conversation is lost
for the journal and the monthly report. Only tables that still hold a non-utf8mb4 collation or column are
touched, so a second run finds nothing to do. MySQL / MariaDB only (SQLite has no charsets).

Run with:
    python migrations/convert_ai_assistant_tables_to_utf8mb4.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine

_TARGET_CHARSET = "utf8mb4"
_TARGET_COLLATION = "utf8mb4_unicode_ci"

_STALE_TABLES_SQL = """
SELECT DISTINCT t.TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES t
LEFT JOIN INFORMATION_SCHEMA.COLUMNS c
       ON c.TABLE_SCHEMA = t.TABLE_SCHEMA
      AND c.TABLE_NAME = t.TABLE_NAME
WHERE t.TABLE_SCHEMA = DATABASE()
  AND t.TABLE_TYPE = 'BASE TABLE'
  AND t.TABLE_NAME LIKE 'ai_assistant%'
  AND (
        t.TABLE_COLLATION NOT LIKE :collation_prefix
     OR (c.CHARACTER_SET_NAME IS NOT NULL AND c.CHARACTER_SET_NAME <> :charset)
      )
ORDER BY t.TABLE_NAME
"""


def run_migration() -> None:
    """Convert the assistant tables still holding a legacy charset."""
    if engine.dialect.name not in {"mysql", "mariadb"}:
        print("[SKIP] convert_ai_assistant_tables_to_utf8mb4: MySQL / MariaDB only")
        return
    with engine.connect() as conn:
        stale_tables = [
            row[0]
            for row in conn.execute(
                text(_STALE_TABLES_SQL),
                {"collation_prefix": f"{_TARGET_CHARSET}%", "charset": _TARGET_CHARSET},
            ).all()
        ]
        if not stale_tables:
            print(f"[OK] every ai_assistant table is already in {_TARGET_CHARSET}")
        for table in stale_tables:
            # Identifiers cannot be bound as parameters; they come from INFORMATION_SCHEMA, not from user input.
            conn.execute(
                text(f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET {_TARGET_CHARSET} COLLATE {_TARGET_COLLATION}")
            )
            print(f"[OK] {table} -> {_TARGET_COLLATION}")
        conn.commit()


if __name__ == "__main__":
    run_migration()
