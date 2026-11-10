"""Create ai_assistant_leads table."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine
from models.ai_assistant_lead import AiAssistantLead


def run_migration() -> None:
    """Create the ai_assistant_leads table if it does not exist."""
    AiAssistantLead.__table__.create(engine, checkfirst=True)


if __name__ == "__main__":
    run_migration()
    print("ai_assistant_leads table ensured.")
