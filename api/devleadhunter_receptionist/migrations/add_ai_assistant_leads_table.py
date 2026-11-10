"""Create ai_assistant_leads table."""

from __future__ import annotations

from core.database import engine
from devleadhunter_receptionist.models.ai_assistant_lead import AiAssistantLead


def run_migration() -> None:
    """Create the ai_assistant_leads table if it does not exist."""
    AiAssistantLead.__table__.create(engine, checkfirst=True)


if __name__ == "__main__":
    run_migration()
    print("ai_assistant_leads table ensured.")
