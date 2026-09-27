"""
The agenda seen from the widget: the slots route, the booking through the lead route, the appointment panel.

Google is a fake client; the database is an in-memory SQLite. Routes are called directly.
"""

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

import api.v1.routes.ai_assistant_widget as routes
import services.ai_assistant.calendar_access as access_module
from enums.assistant_booking_mode import AssistantBookingMode
from enums.assistant_visitor_channel import AssistantVisitorChannel
from models.ai_assistant_appointment import AiAssistantAppointment
from schemas.ai_assistant import AiAssistantBookingChoice, AiAssistantLeadRequest
from services.ai_assistant.chat_service import AiAssistantChatService
from services.ai_assistant.google_calendar_client import GoogleCalendarError
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from tests.assistant_calendar.calendar_fakes import MONDAY_10H, FakeGoogle, add_assistant, add_calendar, paris
from tests.assistant_fakes import VISITOR_REQUEST


@pytest.fixture
def business_clock(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Monday 10:00 in Paris, and the background work recorded instead of run."""
    scheduled: list[int] = []
    monkeypatch.setattr(OpeningHoursCalendar, "business_now", staticmethod(lambda: MONDAY_10H))
    monkeypatch.setattr(routes.ai_assistant_request_service, "schedule_follow_up", lambda request_id: None)
    monkeypatch.setattr(routes.ai_assistant_appointment_notices, "schedule_confirmation", scheduled.append)
    return scheduled


def test_the_slots_route_offers_the_agenda_or_falls_back_on_half_days(
    db: Session, google: FakeGoogle, business_clock: list[int]
) -> None:
    assistant = add_assistant(db)
    add_calendar(db, assistant, appointment_types_json=["Révision"], duration_minutes=30)

    offer = asyncio.run(routes.get_assistant_appointment_slots(assistant.slug, VISITOR_REQUEST, after=None, db=db))
    google.failure = GoogleCalendarError("Google Agenda injoignable")
    access_module.ai_assistant_calendar_access._busy_cache.clear()
    fallback = asyncio.run(routes.get_assistant_appointment_slots(assistant.slug, VISITOR_REQUEST, after=None, db=db))

    assert offer.mode is AssistantBookingMode.CALENDAR
    assert [time.start for time in offer.times] == [paris(22, 10), paris(22, 14), paris(23, 8)]
    assert (offer.types, offer.duration_minutes, offer.max_chosen, offer.has_more) == (["Révision"], 30, 1, True)
    assert fallback.mode is AssistantBookingMode.REQUEST
    assert fallback.times == [] and fallback.days


def test_the_lead_route_books_the_slot_or_answers_409_when_it_was_taken(
    db: Session, google: FakeGoogle, business_clock: list[int]
) -> None:
    assistant = add_assistant(db)
    add_calendar(db, assistant)
    payload = AiAssistantLeadRequest(
        name="Julie Roux",
        contact="06 11 22 33 44",
        session_id="session-1",
        booking=AiAssistantBookingChoice(start=paris(22, 10)),
    )

    answer = asyncio.run(routes.submit_assistant_lead(assistant.slug, payload, VISITOR_REQUEST, db))

    assert answer.booked_start == paris(22, 10)
    [appointment] = db.query(AiAssistantAppointment).all()
    assert business_clock == [appointment.id]
    assert appointment.visitor_phone_e164 == "+33611223344"
    taken = payload.model_copy(update={"session_id": "session-2", "name": "Marc Petit"})
    with pytest.raises(HTTPException) as refused:
        asyncio.run(routes.submit_assistant_lead(assistant.slug, taken, VISITOR_REQUEST, db))
    assert refused.value.status_code == 409


def test_the_chat_opens_the_appointment_panel_when_the_visitor_asks_for_one() -> None:
    asks = AiAssistantChatService.asks_for_appointment

    for message in (
        "Je voudrais prendre rendez-vous mardi",
        "Avez-vous un créneau demain ?",
        "Ik wil een afspraak maken",
        "Ich möchte einen Termin vereinbaren",
        "Can I book an appointment?",
        "Un RDV pour une vidange svp",
    ):
        assert asks(message), message
    for message in ("Le chantier est terminé ?", "Quels sont vos tarifs ?", "Merci beaucoup"):
        assert not asks(message), message


def test_the_widget_learns_how_the_confirmation_leaves(
    db: Session, google: FakeGoogle, business_clock: list[int]
) -> None:
    assistant = add_assistant(db)
    add_calendar(db, assistant)
    by_sms = AiAssistantLeadRequest(
        name="Julie Roux",
        contact="06 11 22 33 44",
        session_id="s-1",
        booking=AiAssistantBookingChoice(start=paris(22, 10)),
    )
    by_nothing = AiAssistantLeadRequest(
        name="Marc Petit",
        contact="03 83 00 00 00",
        session_id="s-2",
        booking=AiAssistantBookingChoice(start=paris(22, 14)),
    )

    sms = asyncio.run(routes.submit_assistant_lead(assistant.slug, by_sms, VISITOR_REQUEST, db))
    nothing = asyncio.run(routes.submit_assistant_lead(assistant.slug, by_nothing, VISITOR_REQUEST, db))

    assert sms.confirmation_channel is AssistantVisitorChannel.SMS
    assert nothing.booked_start == paris(22, 14) and nothing.confirmation_channel is None
