"""Create the ai_assistant_reports table (the monthly reports of the sold assistants)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine
from models.ai_assistant_report import AiAssistantReport


def run_migration() -> None:
    """Create the table if it does not exist (re-runnable)."""
    AiAssistantReport.__table__.create(engine, checkfirst=True)


if __name__ == "__main__":
    run_migration()
