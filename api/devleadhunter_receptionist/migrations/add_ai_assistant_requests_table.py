"""Create the ai_assistant_requests table and copy the legacy assistant leads into it."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine
from models.ai_assistant_request import AiAssistantRequest


def run_migration() -> None:
    """Create the table, then copy each lead not copied yet (re-runnable).

    Legacy leads land as handled history — already notified when captured — so they never
    show up as work to do nor trigger a reminder.
    """
    AiAssistantRequest.__table__.create(engine, checkfirst=True)
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ai_assistant_requests
                    (user_id, prospect_id, assistant_id, type, status, channel, name, contact, need,
                     need_summary, language, handled_at, owner_notified_at, legacy_lead_id, created_at, updated_at)
                SELECT l.user_id, l.prospect_id, l.assistant_id, 'other', 'handled', 'site', l.name, l.contact,
                       l.need, l.need, l.language, l.created_at, l.created_at, l.id, l.created_at, l.created_at
                FROM ai_assistant_leads l
                WHERE NOT EXISTS (SELECT 1 FROM ai_assistant_requests r WHERE r.legacy_lead_id = l.id)
                """
            )
        )
        conn.commit()


if __name__ == "__main__":
    run_migration()
    print("ai_assistant_requests table ensured, legacy leads copied.")
