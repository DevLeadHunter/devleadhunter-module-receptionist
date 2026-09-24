"""Create ``ai_assistant_calendars`` and ``ai_assistant_appointments`` (Google agenda booking)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import engine
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_calendar import AiAssistantCalendar


def run_migration() -> None:
    """Create both tables if they do not exist (re-runnable)."""
    AiAssistantCalendar.__table__.create(engine, checkfirst=True)
    AiAssistantAppointment.__table__.create(engine, checkfirst=True)


if __name__ == "__main__":
    run_migration()
