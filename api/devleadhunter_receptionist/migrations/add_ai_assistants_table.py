"""Create ai_assistants table."""

from __future__ import annotations

from core.database import engine
from devleadhunter_receptionist.models.ai_assistant import AiAssistant


def run_migration() -> None:
    """Create the ai_assistants table if it does not exist."""
    AiAssistant.__table__.create(engine, checkfirst=True)


if __name__ == "__main__":
    run_migration()
    print("ai_assistants table ensured.")
