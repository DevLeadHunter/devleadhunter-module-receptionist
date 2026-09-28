"""
Booking a visitor's pick in a Google agenda: the event and the appointment, the checks, the retries, the cap.

Google is a fake client; the database is an in-memory SQLite. Business time is Paris (UTC+2 in September).
"""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

import services.ai_assistant.calendar_access as access_module
import services.ai_assistant.calendar_service as calendar_module
from enums.ai_assistant_calendar_status import AiAssistantCalendarStatus
from enums.ai_assistant_request import AiAssistantRequestType
from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_calendar import AiAssistantCalendar
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.calendar_booking import AiAssistantCalendarBooking, SlotTakenError
from services.ai_assistant.google_calendar_client import BusyPeriod, GoogleCalendarError
from tests.assistant_calendar.calendar_fakes import (
    MONDAY_10H,
    FakeGoogle,
    add_assistant,
    add_calendar,
    add_request,
    paris,
    utc,
)


def test_a_booking_creates_the_event_and_the_appointment(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant, appointment_types_json=["Révision", "Contrôle technique"])
    request = add_request(db, assistant)

    appointment = asyncio.run(
        AiAssistantCalendarBooking().book(
            db,
            assistant,
            calendar,
            request,
            start=paris(24, 14),
            type_label="révision",
            visitor_phone_e164="+33611223344",
            visitor_email=None,
            now=MONDAY_10H,
        )
    )

    [draft] = google.inserted
    assert appointment.google_event_id == draft.event_id and draft.event_id.startswith("dlh")
    assert (appointment.starts_at, appointment.ends_at) == (utc(paris(24, 14)), utc(paris(24, 15)))
    assert appointment.type_label == "Révision"
    assert draft.summary == "Révision — Julie Roux"
    assert "Contact : 06 11 22 33 44" in draft.description and "Vidange et plaquettes" in draft.description
    # The reminder leaves the day before at the same time (business hours).
    assert appointment.reminder_due_at == utc(paris(23, 14))
    assert google.busy_calls == [(utc(paris(24, 14)), utc(paris(24, 15)))]


def test_a_booking_checks_the_slot_and_the_kind_again(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant, appointment_types_json=["Révision"])
    request = add_request(db, assistant)
    service = AiAssistantCalendarBooking()

    def book(start: datetime, type_label: str | None = "Révision") -> AiAssistantAppointment:
        return asyncio.run(
            service.book(
                db,
                assistant,
                calendar,
                request,
                start=start,
                type_label=type_label,
                visitor_phone_e164=None,
                visitor_email=None,
                now=MONDAY_10H,
            )
        )

    for refused in (paris(22, 10, 10), paris(21, 15), paris(26, 10), paris(22, 12, 30)):
        with pytest.raises(ValueError, match="plus proposé"):
            book(refused)
    with pytest.raises(ValueError, match="type de rendez-vous"):
        book(paris(22, 10), None)
    google.busy = [BusyPeriod(start=utc(paris(22, 10, 30)), end=utc(paris(22, 11)))]
    with pytest.raises(SlotTakenError):
        book(paris(22, 10))
    assert db.query(AiAssistantAppointment).count() == 0
    assert google.inserted == []


def test_one_request_books_one_appointment_and_two_visitors_never_share_a_slot(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant)
    first_request = add_request(db, assistant)
    second_request = add_request(db, assistant, session_id="session-2", name="Marc Petit")
    service = AiAssistantCalendarBooking()

    def book(request: AiAssistantRequest, start: datetime) -> AiAssistantAppointment:
        return asyncio.run(
            service.book(
                db,
                assistant,
                calendar,
                request,
                start=start,
                type_label=None,
                visitor_phone_e164=None,
                visitor_email=None,
                now=MONDAY_10H,
            )
        )

    booked = book(first_request, paris(22, 10))
    again = book(first_request, paris(23, 10))

    assert again.id == booked.id
    assert len(google.inserted) == 1
    # Google does not show it yet: the booking is still refused from the local rows.
    with pytest.raises(SlotTakenError):
        book(second_request, paris(22, 10, 30) - timedelta(minutes=30))


def test_a_booking_the_agenda_refuses_falls_back_on_the_half_day_and_flags_the_agenda(
    db: Session, google: FakeGoogle
) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant)
    request = add_request(db, assistant)
    google.failure = GoogleCalendarError("Google Agenda a refusé l'appel (401)", needs_reconnect=True, status_code=401)

    outcome = asyncio.run(
        AiAssistantCalendarBooking().book_request(
            db, assistant, request, start=paris(24, 14), type_label=None, now=MONDAY_10H
        )
    )

    assert outcome.appointment is None
    assert request.type == AiAssistantRequestType.APPOINTMENT.value
    assert request.appointment_slots_json == [{"date": "2026-09-24", "period": "afternoon"}]
    db.refresh(calendar)
    assert calendar.status == AiAssistantCalendarStatus.ERROR.value
    assert access_module.ai_assistant_calendar_access.usable_calendar(db, assistant) is None


def test_the_visitor_is_told_on_the_channel_they_left(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    service = AiAssistantCalendarBooking()

    assert service.visitor_channels(db, assistant, " 06 11 22 33 44 ") == ("+33611223344", None)
    assert service.visitor_channels(db, assistant, "Julie.Roux@Example.fr") == (None, "julie.roux@example.fr")
    assert service.visitor_channels(db, assistant, "03 83 12 34 56") == (None, None)


def _book(
    db: Session, assistant: AiAssistant, calendar: AiAssistantCalendar, request: AiAssistantRequest, start: datetime
) -> AiAssistantAppointment:
    return asyncio.run(
        AiAssistantCalendarBooking().book(
            db,
            assistant,
            calendar,
            request,
            start=start,
            type_label=None,
            visitor_phone_e164=None,
            visitor_email=None,
            now=MONDAY_10H,
        )
    )


def test_a_lost_insert_answer_is_retried_with_the_same_event_id(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant)
    request = add_request(db, assistant)
    google.insert_failures = [GoogleCalendarError("Google Agenda injoignable")]

    appointment = _book(db, assistant, calendar, request, paris(22, 10))

    assert google.insert_calls == 2
    assert appointment.google_event_id == AiAssistantCalendarBooking._event_id(request.id, utc(paris(22, 10)))
    assert db.query(AiAssistantAppointment).count() == 1


def test_a_taken_slot_empties_the_free_busy_cache(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant)
    access = access_module.ai_assistant_calendar_access
    asyncio.run(calendar_module.ai_assistant_calendar_service.free_slots(db, assistant, calendar, now=MONDAY_10H))
    assert calendar.id in access._busy_cache
    google.busy = [BusyPeriod(start=utc(paris(22, 10)), end=utc(paris(22, 11)))]

    with pytest.raises(SlotTakenError):
        asyncio.run(
            AiAssistantCalendarBooking().book(
                db,
                assistant,
                calendar,
                add_request(db, assistant),
                start=paris(22, 10),
                type_label=None,
                visitor_phone_e164=None,
                visitor_email=None,
                now=MONDAY_10H,
            )
        )

    assert calendar.id not in access._busy_cache


def test_a_refused_insert_is_kept_as_the_agendas_last_problem(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant)
    google.insert_failures = [GoogleCalendarError("Google Agenda a refusé l'appel (403)", status_code=403)]

    with pytest.raises(GoogleCalendarError):
        _book(db, assistant, calendar, add_request(db, assistant), paris(22, 10))

    db.refresh(calendar)
    assert calendar.status == AiAssistantCalendarStatus.CONNECTED.value
    assert "lecture seule" in calendar.last_error
    appointment = _book(db, assistant, calendar, add_request(db, assistant, session_id="session-2"), paris(22, 14))
    db.refresh(calendar)
    assert appointment.google_event_id and calendar.last_error is None


def test_a_day_of_bookings_is_capped_and_the_rest_become_wishes(
    db: Session, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = add_assistant(db)
    add_calendar(db, assistant)
    monkeypatch.setattr(AiAssistantCalendarBooking, "MAX_BOOKINGS_PER_DAY", 1)
    service = AiAssistantCalendarBooking()

    first = asyncio.run(
        service.book_request(
            db, assistant, add_request(db, assistant), start=paris(22, 10), type_label=None, now=MONDAY_10H
        )
    )
    capped_request = add_request(db, assistant, session_id="session-2")
    second = asyncio.run(
        service.book_request(db, assistant, capped_request, start=paris(22, 14), type_label=None, now=MONDAY_10H)
    )

    assert first.appointment is not None and second.appointment is None
    assert capped_request.appointment_slots_json == [{"date": "2026-09-22", "period": "afternoon"}]
    assert len(google.inserted) == 1


def test_only_mobiles_of_the_served_countries_are_texted(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    service = AiAssistantCalendarBooking()

    assert service.visitor_channels(db, assistant, "+32 470 12 34 56") == ("+32470123456", None)
    assert service.visitor_channels(db, assistant, "+44 7700 900123") == (None, None)
    assert service.visitor_channels(db, assistant, "+1 415 555 0100") == (None, None)
