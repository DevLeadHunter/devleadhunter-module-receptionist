"""Fixtures of the agenda tests: the operator's account, a fake Google, the outbox, fresh limits and caches."""

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import api.v1.routes.ai_assistant_client_space as client_routes
import api.v1.routes.ai_assistant_widget as routes
import services.ai_assistant.appointment_notices as notices_module
import services.ai_assistant.calendar_access as access_module
import services.ai_assistant.calendar_service as calendar_module
import services.ai_assistant.client_space_service as client_space_module
import services.ai_assistant.google_calendar_client as google_module
import services.email_sending_service as email_sending_module
import services.sms_service as sms_module
from models.user import User
from services.rate_limiter import SlidingWindowRateLimiter
from tests.assistant_calendar.calendar_fakes import FakeGoogle
from tests.assistant_fakes import AcceptingSmsProvider, AsyncCallRecorder


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session on the test's database, the operator's account (user 7) already in it."""
    session = sessionmaker(bind=engine)()
    session.add(User(id=7, name="Dibodev", email="operateur@dibodev.fr", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> FakeGoogle:
    """A configured Google client that never leaves the process, and a quiet activity log."""
    fake = FakeGoogle()
    for name in ("busy_periods", "insert_event", "get_event", "refresh", "exchange_code", "account_email"):
        monkeypatch.setattr(calendar_module.google_calendar_client, name, getattr(fake, name))
    monkeypatch.setattr(google_module.settings, "google_client_id", "client-id")
    monkeypatch.setattr(google_module.settings, "google_client_secret", "client-secret")
    monkeypatch.setattr(calendar_module.activity_log_service, "record", lambda **_: None)
    monkeypatch.setattr(notices_module.activity_log_service, "record", lambda **_: None)
    monkeypatch.setattr(client_space_module.activity_log_service, "record", lambda **_: None)
    return fake


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mock the email sender and the SMS provider."""
    email = AsyncCallRecorder({"success": True})
    provider = AcceptingSmsProvider()
    monkeypatch.setattr(email_sending_module.EmailSendingService, "send_via_user_identity", email)
    monkeypatch.setattr(sms_module.notification_service, "notify_sms_event", AsyncCallRecorder())
    monkeypatch.setattr(sms_module.sms_service, "_provider", provider)
    return {"email": email, "sms": provider}


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fresh rate limits and an empty free/busy cache for each test."""
    monkeypatch.setattr(client_routes, "assistant_client_limiter", SlidingWindowRateLimiter(120, 300))
    monkeypatch.setattr(routes, "assistant_chat_limiter", SlidingWindowRateLimiter(30, 300))
    monkeypatch.setattr(routes, "assistant_lead_limiter", SlidingWindowRateLimiter(8, 300))
    monkeypatch.setattr(access_module.ai_assistant_calendar_access, "_busy_cache", {})
