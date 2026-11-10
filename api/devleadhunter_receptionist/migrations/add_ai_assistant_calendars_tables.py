"""Create ``ai_assistant_calendars`` and ``ai_assistant_appointments`` (Google agenda booking)."""

from __future__ import annotations

from core.database import engine
from devleadhunter_receptionist.models.ai_assistant_appointment import AiAssistantAppointment
from devleadhunter_receptionist.models.ai_assistant_calendar import AiAssistantCalendar


def run_migration() -> None:
    """Create both tables if they do not exist (re-runnable)."""
    AiAssistantCalendar.__table__.create(engine, checkfirst=True)
    AiAssistantAppointment.__table__.create(engine, checkfirst=True)


if __name__ == "__main__":
    run_migration()
