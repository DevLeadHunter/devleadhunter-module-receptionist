"""
The agenda in the client space: its status, the upcoming appointments, connecting and changing it.

Google is a fake client; the email sender and the SMS provider are mocked; the database is an in-memory
SQLite. Routes are called directly.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

import api.v1.routes.ai_assistant_client_space as client_routes
import services.ai_assistant.google_calendar_client as google_module
from enums.assistant_calendar_status import AssistantCalendarConnection
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_calendar import AiAssistantCalendar
from schemas.ai_assistant_client_space import AiAssistantClientCalendarUpdate
from services.ai_assistant.client_links import AiAssistantClientLinks
from tests.assistant_calendar.calendar_fakes import FakeGoogle, add_assistant, add_calendar, add_request
from tests.assistant_fakes import VISITOR_REQUEST


def test_the_client_space_shows_the_agenda_and_the_upcoming_appointments(
    db: Session, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = add_assistant(db)
    token = AiAssistantClientLinks.token(assistant.id)
    disconnected = asyncio.run(client_routes.get_client_space(token, VISITOR_REQUEST, db))
    add_calendar(db, assistant, appointment_types_json=["Révision"])
    request = add_request(db, assistant)
    start = datetime.now(UTC).replace(tzinfo=None, microsecond=0) + timedelta(days=2)
    db.add(
        AiAssistantAppointment(
            user_id=7,
            assistant_id=assistant.id,
            request_id=request.id,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            type_label="Révision",
            google_event_id="dlhspace",
        )
    )
    db.commit()

    space = asyncio.run(client_routes.get_client_space(token, VISITOR_REQUEST, db))
    monkeypatch.setattr(google_module.settings, "google_client_id", "")
    unavailable = asyncio.run(client_routes.get_client_space(token, VISITOR_REQUEST, db))

    assert disconnected.calendar.status is AssistantCalendarConnection.DISCONNECTED
    assert space.calendar.status is AssistantCalendarConnection.CONNECTED
    assert space.calendar.account_email == "garage.morel@gmail.com"
    assert (space.calendar.duration_minutes, space.calendar.min_notice_hours) == (60, 24)
    assert space.calendar.appointment_types == ["Révision"]
    [upcoming] = space.appointments
    assert (upcoming.name, upcoming.type_label) == ("Julie Roux", "Révision")
    assert space.requests[0].appointment_booked.endswith("(Révision)")
    assert unavailable.calendar.status is AssistantCalendarConnection.UNAVAILABLE


def test_the_client_connects_changes_and_disconnects_the_agenda(
    db: Session, google: FakeGoogle, outbox: dict[str, Any]
) -> None:
    assistant = add_assistant(db)
    token = AiAssistantClientLinks.token(assistant.id)

    consent = asyncio.run(client_routes.connect_client_calendar(token, VISITOR_REQUEST, db))
    state = consent.url.split("state=")[1]
    page = asyncio.run(client_routes.google_calendar_callback(VISITOR_REQUEST, code="ok", state=state, error="", db=db))
    settings = asyncio.run(
        client_routes.update_client_calendar(
            token,
            AiAssistantClientCalendarUpdate(
                duration_minutes=30, min_notice_hours=4, appointment_types=[" Révision ", "révision", "Pneus"]
            ),
            VISITOR_REQUEST,
            db,
        )
    )
    with pytest.raises(HTTPException) as refused:
        asyncio.run(
            client_routes.update_client_calendar(
                token, AiAssistantClientCalendarUpdate(duration_minutes=50), VISITOR_REQUEST, db
            )
        )
    disconnected = asyncio.run(client_routes.disconnect_client_calendar(token, VISITOR_REQUEST, db))

    assert "Google Agenda est connecté" in page.body.decode()
    assert page.headers["referrer-policy"] == "no-referrer"
    [notice] = outbox["email"].calls
    assert notice["subject"] == "Votre agenda Google est connecté"
    assert "garage.morel@gmail.com" in notice["body_html"]
    assert (settings.duration_minutes, settings.min_notice_hours) == (30, 4)
    assert settings.appointment_types == ["Révision", "Pneus"]
    assert refused.value.status_code == 422
    assert disconnected.status is AssistantCalendarConnection.DISCONNECTED
    assert db.query(AiAssistantCalendar).count() == 0


def test_the_callback_page_explains_a_failed_consent(db: Session, google: FakeGoogle) -> None:
    denied = asyncio.run(
        client_routes.google_calendar_callback(VISITOR_REQUEST, code="", state="", error="access_denied", db=db)
    )
    forged = asyncio.run(
        client_routes.google_calendar_callback(
            VISITOR_REQUEST, code="ok", state="9.9.AAAAAAAAAAAAAAAAAAAAAA", error="", db=db
        )
    )

    assert "Connexion annulée" in denied.body.decode()
    assert "Lien de connexion expiré" in forged.body.decode()
    assert db.query(AiAssistantCalendar).count() == 0


def test_long_appointment_kinds_are_cut_not_refused() -> None:
    update = AiAssistantClientCalendarUpdate(appointment_types=["Révision complète " * 5])

    assert len(update.appointment_types[0]) > 40


def test_a_client_link_reaches_only_its_own_agenda(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    other = add_assistant(db)
    add_calendar(db, assistant)
    foreign = add_calendar(db, other, duration_minutes=60)
    token = AiAssistantClientLinks.token(assistant.id)

    asyncio.run(
        client_routes.update_client_calendar(
            token, AiAssistantClientCalendarUpdate(duration_minutes=30), VISITOR_REQUEST, db
        )
    )
    asyncio.run(client_routes.disconnect_client_calendar(token, VISITOR_REQUEST, db))

    db.refresh(foreign)
    assert foreign.duration_minutes == 60
    assert [calendar.assistant_id for calendar in db.query(AiAssistantCalendar).all()] == [other.id]
