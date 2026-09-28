"""
The free slots offered from a Google agenda: the first free one of each half-day, within the business hours.

Google is a fake client; the database is an in-memory SQLite. Business time is Paris (UTC+2 in September).
"""

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from models.ai_assistant_appointment import AiAssistantAppointment
from services.ai_assistant.calendar_service import AiAssistantCalendarService
from services.ai_assistant.calendar_settings import CalendarSettings
from services.ai_assistant.calendar_slot_grid import AiAssistantCalendarSlotGrid
from services.ai_assistant.google_calendar_client import BusyPeriod
from tests.assistant_calendar.calendar_fakes import (
    MONDAY_10H,
    PARIS,
    WEEK,
    FakeGoogle,
    add_assistant,
    add_calendar,
    add_request,
    paris,
    utc,
)


def test_the_offer_leaves_out_slots_already_booked_here(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant)
    request = add_request(db, assistant)
    db.add(
        AiAssistantAppointment(
            user_id=7,
            assistant_id=assistant.id,
            request_id=request.id,
            starts_at=utc(paris(22, 10)),
            ends_at=utc(paris(22, 11)),
            google_event_id="dlhbooked",
        )
    )
    db.commit()

    page = asyncio.run(AiAssistantCalendarService().free_slots(db, assistant, calendar, now=MONDAY_10H))

    assert page.slots[0].start == paris(22, 11)


def _settings(**overrides: Any) -> CalendarSettings:
    values: dict[str, Any] = {
        "calendar_id": "primary",
        "duration_minutes": 60,
        "min_notice_hours": 24,
        "appointment_types": (),
    }
    values.update(overrides)
    return CalendarSettings(**values)


def _starts(page: Any) -> list[datetime]:
    return [slot.start for slot in page.slots]


def test_the_first_free_slot_of_each_half_day_after_the_notice_and_within_the_hours() -> None:
    busy = [BusyPeriod(start=utc(paris(22, 14)), end=utc(paris(22, 15, 30)))]

    page = AiAssistantCalendarSlotGrid.compute_slots(
        opening_hours=WEEK, busy=busy, settings=_settings(), now=MONDAY_10H, after=None, count=3
    )

    assert _starts(page) == [paris(22, 10), paris(22, 15, 30), paris(23, 8)]
    assert page.has_more
    assert page.slots[0].end == paris(22, 11)


def test_the_next_page_starts_at_the_half_day_after_the_last_slot_shown() -> None:
    page = AiAssistantCalendarSlotGrid.compute_slots(
        opening_hours=WEEK, busy=[], settings=_settings(), now=MONDAY_10H, after=paris(23, 8), count=3
    )

    assert _starts(page) == [paris(23, 14), paris(24, 8), paris(24, 14)]


def test_a_slot_never_runs_over_a_closing_time_nor_into_the_weekend() -> None:
    friday_afternoon = datetime(2026, 9, 25, 16, 45, tzinfo=PARIS)

    page = AiAssistantCalendarSlotGrid.compute_slots(
        opening_hours=WEEK,
        busy=[],
        settings=_settings(duration_minutes=90, min_notice_hours=0),
        now=friday_afternoon,
        after=None,
        count=2,
    )

    # 17:00-18:30 would run past 18:00; Saturday and Sunday are closed.
    assert _starts(page) == [paris(28, 8), paris(28, 14)]


def test_unknown_hours_offer_the_weekday_office_hours() -> None:
    page = AiAssistantCalendarSlotGrid.compute_slots(
        opening_hours=None, busy=[], settings=_settings(min_notice_hours=0), now=MONDAY_10H, after=None, count=3
    )

    assert _starts(page) == [paris(21, 10), paris(21, 14), paris(22, 9)]
