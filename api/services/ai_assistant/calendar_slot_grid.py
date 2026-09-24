"""
Where an appointment may start in a client's agenda, with no I/O: on the start grid, within the business hours,
after the minimum notice and clear of the agenda's busy periods.

The widget offers the first free slot of each of the next half-days; a booking is checked again against the same
rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import ClassVar

from services.ai_assistant.appointment_slots import AppointmentRefused
from services.ai_assistant.calendar_settings import CalendarSettings
from services.ai_assistant.google_calendar_client import BusyPeriod
from services.ai_assistant.opening_hours import OpeningHoursCalendar


@dataclass(frozen=True)
class FreeSlot:
    """A free slot, aware in the business time zone."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class SlotPage:
    """The slots offered at once, and whether later half-days have more."""

    slots: list[FreeSlot]
    has_more: bool


class AiAssistantCalendarSlotGrid:
    """The start grid of an agenda's appointments and the rules a start must meet."""

    SLOTS_PER_PAGE: ClassVar[int] = 3
    LOOK_AHEAD_DAYS: ClassVar[int] = 21
    # Candidate starts, business time: the day's first and last possible start.
    FIRST_START: ClassVar[time] = time(6, 0)
    LAST_START: ClassVar[time] = time(21, 30)
    PROBE_MINUTES: ClassVar[int] = 15
    # A slot starting before 13:00 belongs to the morning.
    AFTERNOON_FROM: ClassVar[time] = time(13, 0)
    # Hours of a day whose opening hours are unknown (Monday to Friday only).
    FALLBACK_RANGES: ClassVar[tuple[tuple[time, time], ...]] = ((time(9, 0), time(12, 0)), (time(14, 0), time(18, 0)))

    @classmethod
    def compute_slots(
        cls,
        *,
        opening_hours: list[dict[str, str]] | None,
        busy: list[BusyPeriod],
        settings: CalendarSettings,
        now: datetime,
        after: datetime | None,
        count: int,
    ) -> SlotPage:
        """
        The first free slot of each half-day, from the minimum notice on, within the business hours.

        Args:
            opening_hours: The business's cleaned opening-hour rows, when known.
            busy: The agenda's busy periods, naive UTC.
            settings: The booking settings.
            now: Current business time, aware.
            after: A slot already shown (the page starts at the half-day after it).
            count: How many slots to return.

        Returns:
            At most ``count`` slots, in order, and whether more follow.
        """
        tz = OpeningHoursCalendar.business_timezone()
        local_now = now.astimezone(tz)
        earliest = local_now + timedelta(hours=settings.min_notice_hours)
        duration = timedelta(minutes=settings.duration_minutes)
        grid = cls._grid_minutes(settings.duration_minutes)
        skip_until = cls._half_day(OpeningHoursCalendar.localize(after)) if after is not None else None
        open_cache: dict[datetime, bool] = {}
        slots: list[FreeSlot] = []
        seen: set[tuple[date, int]] = set()
        for offset in range(cls.LOOK_AHEAD_DAYS + 1):
            day = local_now.date() + timedelta(days=offset)
            for start_naive in cls._candidate_starts(day, grid):
                start = start_naive.replace(tzinfo=tz)
                key = cls._half_day(start)
                if key in seen or (skip_until is not None and key <= skip_until) or start < earliest:
                    continue
                end = start + duration
                if not cls._open_throughout(opening_hours, start_naive, duration, open_cache):
                    continue
                if cls.overlaps(busy, start, end):
                    continue
                seen.add(key)
                slots.append(FreeSlot(start=start, end=end))
                if len(slots) > count:
                    return SlotPage(slots=slots[:count], has_more=True)
        return SlotPage(slots=slots, has_more=False)

    @classmethod
    def check_start(
        cls,
        opening_hours: list[dict[str, str]] | None,
        booking_settings: CalendarSettings,
        local_start: datetime,
        local_now: datetime,
    ) -> None:
        """
        Refuse a start the widget would never offer.

        Args:
            opening_hours: The business's cleaned opening-hour rows, when known.
            booking_settings: The agenda's booking settings.
            local_start: The chosen start, aware business time.
            local_now: Current business time, aware.

        Raises:
            AppointmentRefused: When the start is off the grid, too soon, too far or outside the hours.
        """
        grid = cls._grid_minutes(booking_settings.duration_minutes)
        is_on_grid = local_start.second == 0 and local_start.microsecond == 0 and local_start.minute % grid == 0
        is_in_window = (
            local_now + timedelta(hours=booking_settings.min_notice_hours)
            <= local_start
            <= local_now + timedelta(days=cls.LOOK_AHEAD_DAYS + 1)
        )
        is_within_day = cls.FIRST_START <= local_start.time() <= cls.LAST_START
        is_open = cls._open_throughout(
            opening_hours,
            local_start.replace(tzinfo=None),
            timedelta(minutes=booking_settings.duration_minutes),
            {},
        )
        if not (is_on_grid and is_in_window and is_within_day and is_open):
            raise AppointmentRefused("Ce créneau n'est plus proposé")

    @staticmethod
    def overlaps(busy: list[BusyPeriod], start: datetime, end: datetime) -> bool:
        """Whether an aware slot meets a busy period (naive UTC)."""
        start_utc = OpeningHoursCalendar.to_utc(start)
        end_utc = OpeningHoursCalendar.to_utc(end)
        return any(period.start < end_utc and start_utc < period.end for period in busy)

    @classmethod
    def is_morning(cls, moment: datetime) -> bool:
        """Whether a business-time moment falls in the morning half-day."""
        return moment.time() < cls.AFTERNOON_FROM

    @classmethod
    def _half_day(cls, moment: datetime) -> tuple[date, int]:
        """The half-day of a business-time moment (0 morning, 1 afternoon), in calendar order."""
        return moment.date(), 0 if cls.is_morning(moment) else 1

    @staticmethod
    def _grid_minutes(duration_minutes: int) -> int:
        """Starts every 30 minutes, every 15 for the shortest appointments."""
        return 15 if duration_minutes < 30 else 30

    @classmethod
    def _candidate_starts(cls, day: date, grid: int) -> list[datetime]:
        """The possible starts of a day, naive business time."""
        moment = datetime.combine(day, cls.FIRST_START)
        last = datetime.combine(day, cls.LAST_START)
        starts: list[datetime] = []
        while moment <= last:
            starts.append(moment)
            moment += timedelta(minutes=grid)
        return starts

    @classmethod
    def _open_throughout(
        cls,
        opening_hours: list[dict[str, str]] | None,
        start: datetime,
        duration: timedelta,
        cache: dict[datetime, bool],
    ) -> bool:
        """Whether the business is open over the whole slot (probed every 15 minutes, naive business time)."""
        probe = start
        while probe < start + duration:
            if probe not in cache:
                cache[probe] = cls._is_open(opening_hours, probe)
            if not cache[probe]:
                return False
            probe += timedelta(minutes=cls.PROBE_MINUTES)
        return True

    @classmethod
    def _is_open(cls, opening_hours: list[dict[str, str]] | None, moment: datetime) -> bool:
        """Open at a moment; a day with unknown hours is open 9:00-12:00 and 14:00-18:00 on weekdays."""
        answer = OpeningHoursCalendar.is_open_at(opening_hours, moment)
        if answer is not None:
            return answer
        if moment.weekday() >= 5:
            return False
        return any(start <= moment.time() < end for start, end in cls.FALLBACK_RANGES)
