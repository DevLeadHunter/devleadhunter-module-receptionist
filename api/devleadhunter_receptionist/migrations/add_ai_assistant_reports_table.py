"""Create the ai_assistant_reports table (the monthly reports of the sold assistants)."""

from __future__ import annotations

from core.database import engine
from devleadhunter_receptionist.models.ai_assistant_report import AiAssistantReport


def run_migration() -> None:
    """Create the table if it does not exist (re-runnable)."""
    AiAssistantReport.__table__.create(engine, checkfirst=True)


if __name__ == "__main__":
    run_migration()
