"""
Connecting a sold assistant's Google agenda: the consent, the tokens, the HTTP client, the agenda settings.

The HTTP client is tested through an httpx MockTransport, the rest through a fake Google client; the
database is an in-memory SQLite.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import migrations.add_ai_assistant_calendars_tables as calendars_migration
import services.ai_assistant.calendar_service as calendar_module
import services.ai_assistant.google_calendar_client as google_module
from enums.assistant_calendar_status import AssistantCalendarStatus
from models.ai_assistant_calendar import AiAssistantCalendar
from services.ai_assistant.calendar_service import AiAssistantCalendarService, AiAssistantCalendarState
from services.ai_assistant.google_calendar_client import (
    BusyPeriod,
    CalendarEventDraft,
    GoogleCalendarClient,
    GoogleCalendarError,
)
from services.encryption_service import encryption_service
from tests.assistant_calendar.calendar_fakes import (
    GRANTED_SCOPES,
    MONDAY_10H,
    FakeGoogle,
    add_assistant,
    add_calendar,
    paris,
)


def test_the_oauth_state_names_its_assistant_and_expires() -> None:
    now = datetime(2026, 9, 21, 8, 0)
    state = AiAssistantCalendarState.sign(42, now=now)

    assert AiAssistantCalendarState.read(state, now=now + timedelta(minutes=14)) == 42
    assert AiAssistantCalendarState.read(state, now=now + timedelta(minutes=16)) is None
    forged = state.replace("42.", "43.", 1)
    assert AiAssistantCalendarState.read(forged, now=now) is None
    assert AiAssistantCalendarState.read("42.1.abc", now=now) is None


def _client_with(handler: Any, monkeypatch: pytest.MonkeyPatch) -> GoogleCalendarClient:
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(google_module.httpx, "AsyncClient", patched_client)
    monkeypatch.setattr(google_module.settings, "google_client_id", "client-id")
    monkeypatch.setattr(google_module.settings, "google_client_secret", "client-secret")
    return GoogleCalendarClient()


def test_the_consent_url_asks_offline_access_to_the_events_and_the_availability() -> None:
    url = GoogleCalendarClient.authorization_url("7.123.sig")

    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "calendar.events" in url and "calendar.freebusy" in url
    assert "access_type=offline" in url and "prompt=consent" in url and "state=7.123.sig" in url


def test_the_client_reads_tokens_busy_periods_and_events(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "a",
                    "refresh_token": "r",
                    "expires_in": 3599,
                    "scope": " ".join(GRANTED_SCOPES),
                },
            )
        if request.url.path == "/calendar/v3/freeBusy":
            return httpx.Response(
                200,
                json={
                    "calendars": {
                        "primary": {"busy": [{"start": "2026-09-22T12:00:00Z", "end": "2026-09-22T13:30:00Z"}]}
                    }
                },
            )
        return httpx.Response(200, json={"id": json.loads(request.content)["id"]})

    client = _client_with(handler, monkeypatch)
    tokens = asyncio.run(client.exchange_code("code"))
    busy = asyncio.run(
        client.busy_periods("a", "primary", start=datetime(2026, 9, 22, 0, 0), end=datetime(2026, 9, 23, 0, 0))
    )
    draft = CalendarEventDraft(
        event_id="dlh1abc",
        summary="Révision — Julie Roux",
        description="Contact : 06",
        start=paris(22, 10),
        end=paris(22, 11),
        time_zone="Europe/Paris",
        request_id=5,
    )
    event_id = asyncio.run(client.insert_event("a", "agenda du garage@group.calendar.google.com", draft))

    assert (tokens.access_token, tokens.refresh_token) == ("a", "r")
    assert tokens.scopes >= GRANTED_SCOPES
    assert busy == [BusyPeriod(start=datetime(2026, 9, 22, 12, 0), end=datetime(2026, 9, 22, 13, 30))]
    assert json.loads(seen[1].content)["timeMin"] == "2026-09-22T00:00:00Z"
    assert event_id == "dlh1abc"
    body = json.loads(seen[2].content)
    assert body["start"] == {"dateTime": "2026-09-22T10:00:00+02:00", "timeZone": "Europe/Paris"}
    assert "agenda%20du%20garage%40group.calendar.google.com" in str(seen[2].url)


def test_the_client_tells_a_lost_access_from_a_passing_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(
        [
            httpx.Response(400, json={"error": "invalid_grant"}),
            httpx.Response(401, json={"error": {"message": "Invalid Credentials"}}),
            httpx.Response(403, json={"error": {"errors": [{"reason": "rateLimitExceeded"}]}}),
            httpx.Response(409, json={"error": {"errors": [{"reason": "duplicate"}]}}),
            httpx.Response(200, json={"calendars": {"primary": {"errors": [{"reason": "notFound"}]}}}),
        ]
    )
    client = _client_with(lambda request: next(answers), monkeypatch)
    window = {"start": datetime(2026, 9, 22), "end": datetime(2026, 9, 23)}
    draft = CalendarEventDraft(
        event_id="dlh2",
        summary="s",
        description="d",
        start=paris(22, 10),
        end=paris(22, 11),
        time_zone="UTC",
        request_id=1,
    )

    with pytest.raises(GoogleCalendarError) as revoked:
        asyncio.run(client.refresh("r"))
    with pytest.raises(GoogleCalendarError) as unauthorized:
        asyncio.run(client.busy_periods("a", "primary", **window))
    with pytest.raises(GoogleCalendarError) as limited:
        asyncio.run(client.busy_periods("a", "primary", **window))
    duplicate = asyncio.run(client.insert_event("a", "primary", draft))
    with pytest.raises(GoogleCalendarError) as missing:
        asyncio.run(client.busy_periods("a", "primary", **window))

    assert revoked.value.needs_reconnect and unauthorized.value.needs_reconnect
    assert not limited.value.needs_reconnect
    assert duplicate == "dlh2"
    assert "notFound" in str(missing.value)


def test_the_consent_stores_encrypted_tokens_on_a_sold_assistant_only(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    demo = add_assistant(db, status="active")
    service = AiAssistantCalendarService()

    connected_assistant, calendar = asyncio.run(
        service.connect(db, code="ok", state=AiAssistantCalendarState.sign(assistant.id))
    )

    assert connected_assistant.id == assistant.id
    assert calendar.account_email == "garage.morel@gmail.com"
    assert calendar.status == AssistantCalendarStatus.CONNECTED.value
    assert calendar.refresh_token_encrypted and "refresh-1" not in calendar.refresh_token_encrypted
    assert encryption_service.decrypt(calendar.refresh_token_encrypted) == "refresh-1"
    with pytest.raises(ValueError, match="ne peut pas recevoir"):
        asyncio.run(service.connect(db, code="ok", state=AiAssistantCalendarState.sign(demo.id)))
    with pytest.raises(ValueError, match="expiré"):
        asyncio.run(service.connect(db, code="ok", state="1.1.AAAAAAAAAAAAAAAAAAAAAA"))
    with pytest.raises(GoogleCalendarError):
        asyncio.run(service.connect(db, code="refused", state=AiAssistantCalendarState.sign(assistant.id)))


def test_a_consent_without_both_agenda_permissions_stores_nothing(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    google.scopes = frozenset({"openid", google_module.GOOGLE_CALENDAR_EVENTS_SCOPE})

    with pytest.raises(ValueError, match="deux accès"):
        asyncio.run(
            AiAssistantCalendarService().connect(db, code="ok", state=AiAssistantCalendarState.sign(assistant.id))
        )

    assert db.query(AiAssistantCalendar).count() == 0


def test_an_expired_access_token_is_refreshed_and_stored_encrypted(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant, token_expires_at=datetime(2026, 1, 1))

    asyncio.run(AiAssistantCalendarService().free_slots(db, assistant, calendar, now=MONDAY_10H))
    db.rollback()

    assert google.refreshed == ["refresh-0"]
    db.refresh(calendar)
    assert encryption_service.decrypt(calendar.access_token_encrypted) == "fresh-access"


def test_a_token_google_dropped_early_is_refreshed_once_before_the_agenda_is_declared_lost(
    db: Session, google: FakeGoogle
) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant)
    google.busy_failures = [
        GoogleCalendarError("Google Agenda a refusé l'appel (401)", needs_reconnect=True, status_code=401)
    ]

    slots = asyncio.run(
        calendar_module.ai_assistant_calendar_service.free_slots(db, assistant, calendar, now=MONDAY_10H)
    )

    db.refresh(calendar)
    assert slots.slots and google.refreshed == ["refresh-0"]
    assert calendar.status == AssistantCalendarStatus.CONNECTED.value and calendar.last_error is None


def test_an_agenda_id_google_cannot_read_changes_nothing(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    calendar = add_calendar(db, assistant)
    google.failure = GoogleCalendarError("Agenda illisible (notFound)")

    with pytest.raises(ValueError, match="introuvable"):
        asyncio.run(
            AiAssistantCalendarService().update_settings(
                db, calendar, {"calendar_id": "garage@group.calendar.google.com", "duration_minutes": 30}
            )
        )

    db.rollback()
    db.refresh(calendar)
    assert (calendar.calendar_id, calendar.duration_minutes) == ("primary", None)
    google.failure = None
    asyncio.run(
        AiAssistantCalendarService().update_settings(db, calendar, {"calendar_id": "garage@group.calendar.google.com"})
    )
    assert calendar.calendar_id == "garage@group.calendar.google.com"


def test_reconnecting_another_google_account_starts_on_its_main_agenda(db: Session, google: FakeGoogle) -> None:
    assistant = add_assistant(db)
    add_calendar(db, assistant, calendar_id="ancien@group.calendar.google.com")
    google.account = "autre.compte@gmail.com"

    _assistant_again, calendar = asyncio.run(
        AiAssistantCalendarService().connect(db, code="ok", state=AiAssistantCalendarState.sign(assistant.id))
    )

    assert (calendar.account_email, calendar.calendar_id) == ("autre.compte@gmail.com", "primary")


def test_the_migration_creates_both_tables_once(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(calendars_migration, "engine", engine)

    calendars_migration.run_migration()
    calendars_migration.run_migration()

    tables = set(inspect(engine).get_table_names())
    assert {"ai_assistant_calendars", "ai_assistant_appointments"} <= tables
