"""Create ``ai_assistant_documents``: the documents a business gives its assistant, in utf8mb4."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text

from core.database import engine
from models.ai_assistant_document import AiAssistantDocument

_TABLE = AiAssistantDocument.__tablename__


def run_migration() -> None:
    """Create the table if it does not exist (re-runnable), and bring it to utf8mb4 if it was created otherwise."""
    AiAssistantDocument.__table__.create(engine, checkfirst=True)
    if engine.dialect.name != "mysql":
        return
    with engine.begin() as conn:
        collation = conn.execute(
            text(
                "SELECT TABLE_COLLATION FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
            ),
            {"table": _TABLE},
        ).scalar()
        # A table made by an earlier create_all took the schema's default charset (latin1 on older databases).
        if collation and not str(collation).startswith("utf8mb4"):
            conn.execute(text(f"ALTER TABLE `{_TABLE}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            print(f"  + {_TABLE} -> utf8mb4_unicode_ci")


if __name__ == "__main__":
    run_migration()
