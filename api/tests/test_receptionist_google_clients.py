"""The receptionist's Google Calendar client over HTTP, beside the core's Google integrations: Google is never called,
its answers come from an httpx MockTransport."""

import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

import devleadhunter_receptionist.services.google_calendar_client as google_module
import services.google_oauth_client as oauth_module
from devleadhunter_receptionist.services.google_calendar_client import CalendarEventState, GoogleCalendarClient
from devleadhunter_receptionist.settings import receptionist_settings
from services.gmail_oauth_service import GmailOAuthService


def _calendar_client_with(handler: Any, monkeypatch: pytest.MonkeyPatch) -> GoogleCalendarClient:
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(google_module.httpx, "AsyncClient", patched_client)
    monkeypatch.setattr(oauth_module.settings, "google_client_id", "client-id")
    monkeypatch.setattr(oauth_module.settings, "google_client_secret", "client-secret")
    return GoogleCalendarClient()


def test_the_calendar_client_reads_back_an_event_it_created(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reminder and the booking recovery read our event: still there, moved, cancelled or gone."""
    requested: list[str] = []
    answers = iter(
        [
            httpx.Response(200, json={"status": "confirmed", "start": {"dateTime": "2026-09-24T14:00:00+02:00"}}),
            httpx.Response(200, json={"status": "cancelled"}),
            httpx.Response(410, json={"error": {"message": "Resource has been deleted"}}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.raw_path.decode())
        return next(answers)

    client = _calendar_client_with(handler, monkeypatch)
    standing = asyncio.run(client.get_event("a", "agenda du garage@group.calendar.google.com", "dlh1abc"))
    cancelled = asyncio.run(client.get_event("a", "primary", "dlh1abc"))
    deleted = asyncio.run(client.get_event("a", "primary", "dlh1abc"))

    assert standing == CalendarEventState(cancelled=False, start=datetime(2026, 9, 24, 12, 0))
    assert cancelled == CalendarEventState(cancelled=True, start=None)
    assert deleted is None
    assert requested[0] == "/calendar/v3/calendars/agenda%20du%20garage%40group.calendar.google.com/events/dlh1abc"


@pytest.fixture
def google_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The server's Google OAuth client, with one redirect address per integration."""
    monkeypatch.setattr(oauth_module.settings, "google_client_id", "client-id")
    monkeypatch.setattr(oauth_module.settings, "google_client_secret", "client-secret")
    monkeypatch.setattr(oauth_module.settings, "google_redirect_uri", "https://api.test/gmail/callback")
    monkeypatch.setattr(receptionist_settings, "google_calendar_redirect_uri", "https://api.test/calendar/callback")


def _serve_google(handler: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer every Google call of the shared OAuth client through a mock transport."""
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(oauth_module.httpx, "AsyncClient", patched_client)


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


@pytest.mark.usefixtures("google_settings")
def test_the_calendar_asks_its_own_redirect_address_and_keeps_the_scopes_already_granted() -> None:
    gmail = _query(GmailOAuthService().get_authorization_url(state="user_7"))
    calendar = _query(GoogleCalendarClient.authorization_url("7.123.sig"))

    assert calendar["redirect_uri"] == ["https://api.test/calendar/callback"]
    assert calendar["include_granted_scopes"] == ["true"] and "include_granted_scopes" not in gmail
    assert calendar["client_id"] == ["client-id"]
    assert (calendar["access_type"], calendar["prompt"], calendar["response_type"]) == (
        ["offline"],
        ["consent"],
        ["code"],
    )


@pytest.mark.usefixtures("google_settings")
def test_the_calendar_reads_the_account_profile_with_its_own_token(monkeypatch: pytest.MonkeyPatch) -> None:
    authorizations: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        authorizations.append(request.headers["authorization"])
        return httpx.Response(200, json={"email": "garage@gmail.com", "verified_email": True, "name": "Garage"})

    _serve_google(handler, monkeypatch)
    calendar_email = asyncio.run(GoogleCalendarClient().account_email("calendar-token"))

    assert calendar_email == "garage@gmail.com"
    assert authorizations == ["Bearer calendar-token"]
