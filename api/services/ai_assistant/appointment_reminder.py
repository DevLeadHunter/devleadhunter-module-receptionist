"""
When a visitor's J-1 reminder leaves: the day before, at the appointment's time, between 9:00 and 19:00.

The booking plans it in that window (``due_at``); the sending pass still sends it until 20:00 (``is_sending_time``).
The hour of margin covers a pass that runs late (a restart, an agenda slow to answer), never a reminder at night.
A reminder that would come less than two hours after the booking is not planned.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import ClassVar

from services.ai_assistant.opening_hours import OpeningHoursCalendar


class AppointmentReminderWindow:
    """The J-1 reminder's rule, in business time: planned at the booking, checked again when it leaves."""

    HOURS_BEFORE: ClassVar[int] = 24
    EARLIEST: ClassVar[time] = time(9, 0)
    LATEST_PLANNED: ClassVar[time] = time(19, 0)
    LATEST_SENT: ClassVar[time] = time(20, 0)
    MIN_GAP_AFTER_BOOKING: ClassVar[timedelta] = timedelta(hours=2)

    @classmethod
    def due_at(cls, start_utc: datetime, *, booked_at: datetime) -> datetime | None:
        """
        When the visitor's J-1 reminder leaves: 24 hours before, kept between 9:00 and 19:00 (business time).

        Args:
            start_utc: The appointment's start, naive UTC.
            booked_at: When it was booked, naive UTC.

        Returns:
            The due moment, naive UTC, or None when it would come less than 2 hours after the booking.
        """
        tz = OpeningHoursCalendar.business_timezone()
        due = OpeningHoursCalendar.to_business_time(start_utc) - timedelta(hours=cls.HOURS_BEFORE)
        if due.time() < cls.EARLIEST:
            due = datetime.combine(due.date(), cls.EARLIEST, tzinfo=tz)
        elif due.time() > cls.LATEST_PLANNED:
            due = datetime.combine(due.date(), cls.LATEST_PLANNED, tzinfo=tz)
        due_utc = OpeningHoursCalendar.to_utc(due)
        return due_utc if due_utc > booked_at + cls.MIN_GAP_AFTER_BOOKING else None

    @classmethod
    def is_sending_time(cls, local_now: datetime) -> bool:
        """
        Whether a due reminder may leave now: from 9:00 to 20:00 (business time), never at night.

        Args:
            local_now: Current business time.

        Returns:
            True inside the sending window.
        """
        return cls.EARLIEST <= local_now.time().replace(tzinfo=None) < cls.LATEST_SENT
