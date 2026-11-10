"""The booking settings of a client's agenda: the agenda used, the length of an appointment, the notice, the kinds."""

from __future__ import annotations

from dataclasses import dataclass

from models.ai_assistant_calendar import AiAssistantCalendar

DEFAULT_DURATION_MINUTES = 60
DEFAULT_MIN_NOTICE_HOURS = 24
DURATION_CHOICES: tuple[int, ...] = (15, 30, 45, 60, 90, 120, 180)
MIN_NOTICE_CHOICES: tuple[int, ...] = (0, 2, 4, 12, 24, 48, 72)
MAX_APPOINTMENT_TYPES = 6
APPOINTMENT_TYPE_MAX_CHARS = 40


@dataclass(frozen=True)
class CalendarSettings:
    """The booking settings of an agenda, defaults applied."""

    calendar_id: str
    duration_minutes: int
    min_notice_hours: int
    appointment_types: tuple[str, ...]

    @classmethod
    def defaults(cls) -> CalendarSettings:
        """The settings of an agenda nobody changed."""
        return cls(
            calendar_id="primary",
            duration_minutes=DEFAULT_DURATION_MINUTES,
            min_notice_hours=DEFAULT_MIN_NOTICE_HOURS,
            appointment_types=(),
        )

    @classmethod
    def of(cls, calendar: AiAssistantCalendar) -> CalendarSettings:
        """
        Read an agenda's settings.

        Args:
            calendar: The connected agenda.

        Returns:
            Its settings; ``NULL`` columns read as the defaults.
        """
        types = calendar.appointment_types_json if isinstance(calendar.appointment_types_json, list) else []
        return cls(
            calendar_id=calendar.calendar_id or "primary",
            duration_minutes=calendar.duration_minutes or DEFAULT_DURATION_MINUTES,
            min_notice_hours=(
                DEFAULT_MIN_NOTICE_HOURS if calendar.min_notice_hours is None else calendar.min_notice_hours
            ),
            appointment_types=tuple(str(label) for label in types if str(label).strip()),
        )
