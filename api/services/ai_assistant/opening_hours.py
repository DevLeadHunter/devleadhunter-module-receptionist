"""
Whether a business is open at a given moment, from the opening hours of its knowledge.

The rows are the cleaned Google Maps hours stored in ``knowledge_json['opening_hours']``
(``[{"day": "lundi", "hours": "08:00–12:00, 14:00–18:00"}]``). A request received while the
business is closed is exactly what the receptionist catches for it, so the answer never
guesses: no rows, no row for the day or unreadable hours mean unknown (``None``), never closed.
"""

from __future__ import annotations

import calendar
import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo
from functools import lru_cache
from typing import ClassVar

from services.text_normalizer import TextNormalizer

try:  # Every targeted country (FR, BE, LU, CH) keeps Paris time; UTC when tzdata is missing.
    from zoneinfo import ZoneInfo

    _BUSINESS_TIMEZONE: ZoneInfo | None = ZoneInfo("Europe/Paris")
except Exception:
    _BUSINESS_TIMEZONE = None

_MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class ClosedHoursEstimate:
    """How long a business is closed while its customers look for it (7:00 to 22:00), from its opening hours."""

    open_hours_per_week: int
    # Share of the 7:00–22:00 window of a week when the business is closed, in %.
    closed_share_pct: int
    # Hours of the 7:00–22:00 window when the business is closed, over a whole month.
    closed_hours_in_month: int


class OpeningHoursCalendar:
    """Reads opening-hour rows to tell whether the business is open at a local moment."""

    # Indexed like datetime.weekday(): Monday = 0. Rows are French; the others cover BE/LU/CH listings.
    WEEKDAY_NAMES: ClassVar[tuple[tuple[str, ...], ...]] = (
        ("lundi", "monday", "maandag", "montag"),
        ("mardi", "tuesday", "dinsdag", "dienstag"),
        ("mercredi", "wednesday", "woensdag", "mittwoch"),
        ("jeudi", "thursday", "donderdag", "donnerstag"),
        ("vendredi", "friday", "vrijdag", "freitag"),
        ("samedi", "saturday", "zaterdag", "samstag"),
        ("dimanche", "sunday", "zondag", "sonntag"),
    )
    CLOSED_MARKERS: ClassVar[tuple[str, ...]] = ("ferme", "closed", "gesloten", "geschlossen")
    ALWAYS_OPEN_MARKERS: ClassVar[tuple[str, ...]] = (
        "24h/24",
        "24 h/24",
        "24h24",
        "24 heures",
        "24 hours",
        "24 uur",
        "24 stunden",
    )
    _RANGE_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(\d{1,2})\s*[:h.]\s*(\d{2})?\s*(?:[-–—]|\ba\b|\bto\b|\btot\b|\bbis\b)\s*(\d{1,2})\s*[:h.]?\s*(\d{2})?"
    )
    # When customers look for a business (and write to it), for the closed-hours estimate.
    DAYTIME_FROM_MINUTE: ClassVar[int] = 7 * 60
    DAYTIME_UNTIL_MINUTE: ClassVar[int] = 22 * 60
    _ESTIMATE_STEP_MINUTES: ClassVar[int] = 15

    @staticmethod
    def business_now() -> datetime:
        """Current local time of the business (Paris time; UTC when tzdata is missing)."""
        return datetime.now(_BUSINESS_TIMEZONE) if _BUSINESS_TIMEZONE else datetime.now(UTC)

    @staticmethod
    def business_timezone() -> tzinfo:
        """The business time zone (Paris; UTC when tzdata is missing)."""
        return _BUSINESS_TIMEZONE or UTC

    @staticmethod
    def to_business_time(utc_moment: datetime) -> datetime:
        """
        Convert a naive UTC timestamp (as stored in the database) to the business's local time.

        Args:
            utc_moment: Naive UTC datetime.

        Returns:
            The same instant in Paris time (UTC when tzdata is missing).
        """
        aware = utc_moment.replace(tzinfo=UTC)
        return aware.astimezone(_BUSINESS_TIMEZONE) if _BUSINESS_TIMEZONE else aware

    @classmethod
    def is_open_at(cls, opening_hours: list[dict[str, str]] | None, moment: datetime) -> bool | None:
        """
        Whether the business is open at a local moment.

        Args:
            opening_hours: Cleaned rows ``[{"day": ..., "hours": ...}]``.
            moment: Local time of the business.

        Returns:
            True or False when the hours say so; None when they are missing or unreadable.
        """
        return cls._is_open(cls._hours_by_weekday(opening_hours), moment)

    @classmethod
    def closed_hours_estimate(
        cls, opening_hours: list[dict[str, str]] | None, *, year: int, month: int
    ) -> ClosedHoursEstimate | None:
        """
        How long the business is closed from 7:00 to 22:00, over a week and over a month.

        Args:
            opening_hours: Cleaned rows ``[{"day": ..., "hours": ...}]``.
            year: The month's year.
            month: The month (1 to 12).

        Returns:
            The estimate, or None when a day of the week has no readable hours, or when the listing shows a holiday
            week (a row flagged ``holiday``: that week's hours, not the usual ones).
        """
        if any(isinstance(row, dict) and row.get("holiday") for row in opening_hours or []):
            return None
        hours_by_weekday = cls._hours_by_weekday(opening_hours)
        step = cls._ESTIMATE_STEP_MINUTES
        monday = datetime(2024, 1, 1)  # Any Monday: only the weekday and the time of day matter.
        open_minutes = 0
        closed_daytime_by_weekday: list[int] = []
        for weekday in range(7):
            closed_daytime = 0
            for minute in range(0, _MINUTES_PER_DAY, step):
                is_open = cls._is_open(hours_by_weekday, monday + timedelta(days=weekday, minutes=minute))
                if is_open is None:
                    return None
                if is_open:
                    open_minutes += step
                elif cls.DAYTIME_FROM_MINUTE <= minute < cls.DAYTIME_UNTIL_MINUTE:
                    closed_daytime += step
            closed_daytime_by_weekday.append(closed_daytime)
        daytime_per_week = 7 * (cls.DAYTIME_UNTIL_MINUTE - cls.DAYTIME_FROM_MINUTE)
        days_in_month = calendar.monthrange(year, month)[1]
        closed_in_month = sum(
            closed_daytime_by_weekday[date(year, month, day).weekday()] for day in range(1, days_in_month + 1)
        )
        return ClosedHoursEstimate(
            open_hours_per_week=_round_half_up(open_minutes / 60),
            closed_share_pct=_round_half_up(100 * sum(closed_daytime_by_weekday) / daytime_per_week),
            closed_hours_in_month=_round_half_up(closed_in_month / 60),
        )

    @classmethod
    def _is_open(cls, hours_by_weekday: dict[int, str], moment: datetime) -> bool | None:
        """Whether the business is open at a local moment, from its hours by weekday (see ``is_open_at``)."""
        if not hours_by_weekday:
            return None
        minute_of_day = moment.hour * 60 + moment.minute

        # A range past midnight the day before (e.g. 18:00–02:00) still covers the early hours.
        previous_day = hours_by_weekday.get((moment.weekday() - 1) % 7)
        if previous_day is not None:
            for _start, end in cls._ranges(previous_day):
                if end > _MINUTES_PER_DAY and minute_of_day < end - _MINUTES_PER_DAY:
                    return True

        today = hours_by_weekday.get(moment.weekday())
        if today is None:
            return None
        if any(marker in today for marker in cls.ALWAYS_OPEN_MARKERS):
            return True
        if any(marker in today for marker in cls.CLOSED_MARKERS):
            return False
        ranges = cls._ranges(today)
        if not ranges:
            return None
        return any(start <= minute_of_day < end for start, end in ranges)

    @classmethod
    def received_outside_hours(cls, opening_hours: list[dict[str, str]] | None, moment: datetime) -> bool | None:
        """
        Whether something received at this local moment came in while the business was closed.

        Args:
            opening_hours: Cleaned rows ``[{"day": ..., "hours": ...}]``.
            moment: Local time of the business.

        Returns:
            True when closed, False when open, None when the hours cannot tell.
        """
        is_open = cls.is_open_at(opening_hours, moment)
        return None if is_open is None else not is_open

    @classmethod
    def _hours_by_weekday(cls, opening_hours: list[dict[str, str]] | None) -> dict[int, str]:
        """Map each weekday (Monday = 0) to its normalized hours text; the first row of a day wins."""
        hours_by_weekday: dict[int, str] = {}
        for row in opening_hours or []:
            if not isinstance(row, dict):
                continue
            day = cls._normalize(str(row.get("day") or ""))
            for weekday, names in enumerate(cls.WEEKDAY_NAMES):
                if day.startswith(names) and weekday not in hours_by_weekday:
                    hours_by_weekday[weekday] = cls._normalize(str(row.get("hours") or ""))
                    break
        return hours_by_weekday

    @classmethod
    def _ranges(cls, hours: str) -> tuple[tuple[int, int], ...]:
        """Opening ranges of one day in minutes; a range past midnight ends after 1440."""
        return _parse_ranges(hours)

    @staticmethod
    def _normalize(text: str) -> str:
        """Lower-case, accent-free, single-spaced text."""
        return " ".join(TextNormalizer.fold(text).split())


@lru_cache(maxsize=512)
def _parse_ranges(hours: str) -> tuple[tuple[int, int], ...]:
    """Opening ranges of one day's normalized hours text, in minutes (the same few texts come back all the time)."""
    ranges: list[tuple[int, int]] = []
    for match in OpeningHoursCalendar._RANGE_PATTERN.finditer(hours):
        start_hour, start_minute, end_hour, end_minute = match.groups()
        if int(start_hour) > 24 or int(end_hour) > 24:
            continue
        start = int(start_hour) * 60 + int(start_minute or 0)
        end = int(end_hour) * 60 + int(end_minute or 0)
        if end <= start:
            end += _MINUTES_PER_DAY
        ranges.append((start, end))
    return tuple(ranges)


def _round_half_up(value: float) -> int:
    """Round as a reader does (12.5 → 13), not to the even neighbour."""
    return math.floor(value + 0.5)
