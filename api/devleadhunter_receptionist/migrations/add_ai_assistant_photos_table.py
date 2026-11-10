"""Create the ai_assistant_photos table (the photos visitors send for a quote)."""

from __future__ import annotations

from core.database import engine
from devleadhunter_receptionist.models.ai_assistant_photo import AiAssistantPhoto


def run_migration() -> None:
    """Create the table if it does not exist (re-runnable)."""
    AiAssistantPhoto.__table__.create(engine, checkfirst=True)


if __name__ == "__main__":
    run_migration()
