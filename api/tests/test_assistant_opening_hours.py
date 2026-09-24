"""Unit tests for « reçue hors horaires » on an assistant request.

The hours come from the Google Maps rows of the assistant's knowledge. The rule
that matters most: missing or unreadable hours are unknown, never "closed" — a
request is only counted outside hours when the hours say the business was shut.
"""

from datetime import datetime

import pytest

from services.ai_assistant.opening_hours import ClosedHoursEstimate, OpeningHoursCalendar

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


def test_the_closed_hours_estimate_counts_the_closed_daytime_of_a_week_and_a_month() -> None:
    estimate = OpeningHoursCalendar.closed_hours_estimate(_WEEK, year=2026, month=9)

    # Open: Mon, Tue, Thu 8 h, Wed 4 h, Fri 18:00–24:00, Sat 0:00–2:00 (Friday night), Sun 24 h = 60 h.
    # Closed from 7:00 to 22:00: 7 + 7 + 11 + 7 + 11 + 15 + 0 = 58 h of 105 (55 %); September 2026 has five
    # Tuesdays and five Wednesdays: 4 × 7 + 5 × 7 + 5 × 11 + 4 × 7 + 4 × 11 + 4 × 15 = 250 h.
    assert estimate == ClosedHoursEstimate(open_hours_per_week=60, closed_share_pct=55, closed_hours_in_month=250)
    assert OpeningHoursCalendar.closed_hours_estimate(_WEEK[:6], year=2026, month=9) is None
    assert OpeningHoursCalendar.closed_hours_estimate(None, year=2026, month=9) is None


def test_the_estimate_counts_an_overnight_range_and_skips_a_holiday_week() -> None:
    from services.ai_assistant.knowledge_builder import ai_assistant_knowledge_builder

    days = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
    night_shift = [{"day": day, "hours": "20:00–08:00"} for day in days]
    holiday_week = [{"day": day, "hours": "08:00–18:00"} for day in days[:5]] + [
        {"day": "samedi (Armistice 1918)", "hours": "Fermé"},
        {"day": "dimanche", "hours": "Fermé"},
    ]
    knowledge = ai_assistant_knowledge_builder.build_knowledge(
        business_name="Plomberie Dupont", enrichment={"opening_hours": holiday_week}
    )

    # Open 0:00–8:00 and 20:00–24:00 every day (84 h); from 7:00 to 22:00, open 7–8 and 20–22: closed 12 h of 15.
    assert OpeningHoursCalendar.closed_hours_estimate(night_shift, year=2026, month=9) == ClosedHoursEstimate(
        open_hours_per_week=84, closed_share_pct=80, closed_hours_in_month=360
    )
    # Around a public holiday, Google shows that week's hours: no estimate from them.
    assert knowledge["opening_hours"][5] == {"day": "samedi", "hours": "Fermé", "holiday": True}
    assert "holiday" not in knowledge["opening_hours"][6]
    assert OpeningHoursCalendar.closed_hours_estimate(knowledge["opening_hours"], year=2026, month=11) is None
    assert OpeningHoursCalendar.is_open_at(knowledge["opening_hours"], _at(0, 9)) is True
