"""Fixtures of the mailbox tests: the operator's account, a fake Gmail and model, the outbox, a quiet activity log."""

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import api.v1.routes.ai_assistant_client_space as client_routes
import services.activity_log_service as activity_module
import services.ai_assistant.gmail_client as gmail_module
import services.ai_assistant.llm_router as llm_router_module
import services.ai_assistant.request_follow_up as follow_up_module
import services.email_sending_service as email_sending_module
import services.sms_service as sms_module
from models.user import User
from services.rate_limiter import SlidingWindowRateLimiter
from tests.assistant_fakes import AcceptingSmsProvider, AsyncCallRecorder
from tests.assistant_mailbox.mailbox_fakes import FakeGmail, FakeModel

_FAKED_CALLS: tuple[str, ...] = (
    "get_profile",
    "changes_since",
    "recent_inbox",
    "get_message",
    "create_draft",
    "refresh",
    "exchange_code",
    "revoke",
)


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
def gmail(monkeypatch: pytest.MonkeyPatch) -> FakeGmail:
    """A configured Gmail that never leaves the process, and a quiet activity log."""
    fake = FakeGmail()
    for name in _FAKED_CALLS:
        monkeypatch.setattr(gmail_module.gmail_client, name, getattr(fake, name))
    monkeypatch.setattr(gmail_module.settings, "google_client_id", "client-id")
    monkeypatch.setattr(gmail_module.settings, "google_client_secret", "client-secret")
    monkeypatch.setattr(
        gmail_module.settings,
        "google_mailbox_redirect_uri",
        "https://api.example.fr/api/v1/ai-assistants/mailbox/google/callback",
    )
    monkeypatch.setattr(activity_module.activity_log_service, "record", lambda **_: None)
    return fake


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    """The model of the triage and of the replies, answering on cue."""
    fake = FakeModel()
    monkeypatch.setattr(llm_router_module.assistant_llm_router, "complete_json", fake.complete_json)
    monkeypatch.setattr(llm_router_module.assistant_llm_router, "chat", fake.chat)
    return fake


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mock the email sender, the operator's push and the SMS provider."""
    email = AsyncCallRecorder({"success": True})
    push = AsyncCallRecorder()
    provider = AcceptingSmsProvider()
    monkeypatch.setattr(email_sending_module.EmailSendingService, "send_via_user_identity", email)
    monkeypatch.setattr(follow_up_module.notification_service, "notify_assistant_lead", push)
    monkeypatch.setattr(sms_module.notification_service, "notify_sms_event", AsyncCallRecorder())
    monkeypatch.setattr(sms_module.sms_service, "_provider", provider)
    return {"email": email, "push": push, "sms": provider}


@pytest.fixture(autouse=True)
def fresh_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fresh client-space rate limits for each test."""
    monkeypatch.setattr(client_routes, "assistant_client_limiter", SlidingWindowRateLimiter(120, 300))
