"""Create ``ai_assistant_mailboxes`` and ``ai_assistant_mailbox_messages`` (Gmail reply drafts), in utf8mb4."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text

from core.database import engine
from models.ai_assistant_mailbox import AiAssistantMailbox
from models.ai_assistant_mailbox_message import AiAssistantMailboxMessage

_MODELS: tuple[type, ...] = (AiAssistantMailbox, AiAssistantMailboxMessage)


def run_migration() -> None:
    """Create both tables if they do not exist (re-runnable), and bring them to utf8mb4 if created otherwise."""
    for model in _MODELS:
        model.__table__.create(engine, checkfirst=True)
    if engine.dialect.name != "mysql":
        return
    with engine.begin() as conn:
        for model in _MODELS:
            table = model.__tablename__
            collation = conn.execute(
                text(
                    "SELECT TABLE_COLLATION FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
                ),
                {"table": table},
            ).scalar()
            # A table made by an earlier create_all took the schema's default charset (latin1 on older databases).
            if collation and not str(collation).startswith("utf8mb4"):
                conn.execute(text(f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                print(f"  + {table} -> utf8mb4_unicode_ci")


if __name__ == "__main__":
    run_migration()
