"""Unit tests for « reçue hors horaires » on an assistant request.

The hours come from the Google Maps rows of the assistant's knowledge. The rule
that matters most: missing or unreadable hours are unknown, never "closed" — a
request is only counted outside hours when the hours say the business was shut.
"""

from datetime import datetime

import pytest

from services.ai_assistant.opening_hours import OpeningHoursCalendar

_WEEK = [
    {"day": "lundi", "hours": "08:00–12:00, 14:00–18:00"},
    {"day": "mardi", "hours": "08:00–12:00, 14:00–18:00"},
    {"day": "mercredi", "hours": "8 h 00 à 12 h 00"},
    {"day": "jeudi", "hours": "08:00–12:00, 14:00–18:00"},
    {"day": "vendredi", "hours": "18:00–02:00"},
    {"day": "samedi(Assomption)", "hours": "Fermé"},
    {"day": "Dimanche", "hours": "Ouvert 24h/24"},
]


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    """A local moment in the week of Monday 21 September 2026 (day 0 = Monday)."""
    return datetime(2026, 9, 21 + day, hour, minute)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (_at(0, 9), False),
        (_at(0, 12, 30), True),
        (_at(0, 7, 59), True),
        (_at(0, 18), True),
        (_at(2, 11, 59), False),
        (_at(2, 13), True),
        (_at(4, 23), False),
        (_at(5, 1, 30), False),
        (_at(5, 10), True),
        (_at(6, 3), False),
    ],
)
def test_requests_are_outside_hours_only_when_the_business_is_shut(moment: datetime, expected: bool) -> None:
    assert OpeningHoursCalendar.received_outside_hours(_WEEK, moment) is expected


@pytest.mark.parametrize("hours", [None, [], [{"day": "lundi", "hours": "Horaires variables"}], ["lundi 8-18"]])
def test_missing_or_unreadable_hours_are_unknown(hours: list | None) -> None:
    assert OpeningHoursCalendar.received_outside_hours(hours, _at(0, 9)) is None


def test_a_day_without_row_is_unknown() -> None:
    assert OpeningHoursCalendar.received_outside_hours([{"day": "lundi", "hours": "08:00–18:00"}], _at(1, 9)) is None


def test_business_now_is_timezone_aware() -> None:
    assert OpeningHoursCalendar.business_now().tzinfo is not None
