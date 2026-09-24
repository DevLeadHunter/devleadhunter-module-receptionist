"""Tests for the structured requests captured by an assistant (« Demandes »).

A visitor who leaves their details becomes one request per widget session: linked to the
conversation, typed and summarized, flagged when it came in outside the business hours, and
announced once (summary email to the business only once the assistant is sold, push to the
operator). Everything runs on in-memory SQLite with the model, the email and the push mocked.
"""

import asyncio
import importlib
import pkgutil
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import migrations.add_ai_assistant_requests_table as requests_migration
import models
import services.ai_assistant.request_analyzer as analyzer_module
import services.ai_assistant.request_service as request_module
import services.email_sending_service as email_sending_module
from core.database import Base
from enums.ai_assistant_request import AiAssistantRequestStatus, AiAssistantRequestType
from models.ai_assistant import AiAssistant
from models.ai_assistant_lead import AiAssistantLead
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.conversation_service import ai_assistant_conversation_service
from services.ai_assistant.request_analyzer import TranscriptLine
from services.ai_assistant.request_email import AiAssistantRequestEmail, RequestEmailContent
from services.ai_assistant.request_links import AiAssistantRequestLinks
from services.ai_assistant.request_service import AiAssistantRequestService

# Load every model so SQLAlchemy can configure the mappers (relationships resolve across models).
for _module in pkgutil.iter_modules(models.__path__):
    importlib.import_module("models." + _module.name)

_HOURS = [{"day": "lundi", "hours": "08:00–12:00, 14:00–18:00"}]
_MONDAY_EVENING = datetime(2026, 9, 21, 21, 30)
_MONDAY_MORNING = datetime(2026, 9, 21, 9, 0)


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(engine) -> Session:
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _assistant(db: Session, *, status: str = "active", email: str | None = None) -> AiAssistant:
    prospect = ProspectDB(
        name="Toitures Morel",
        category="Couvreur",
        source="google",
        confidence=2,
        user_id=7,
        email="contact@toitures-morel.fr",
    )
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Toitures Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.knowledge_json = {**(assistant.knowledge_json or {}), "opening_hours": _HOURS}
    assistant.status = status
    assistant.email = email
    db.commit()
    return assistant


def _capture(db: Session, assistant: AiAssistant, **overrides: Any) -> tuple[AiAssistantRequest, bool]:
    values: dict[str, Any] = {
        "name": "  Claire Martin ",
        "contact": " 06 12 34 56 78 ",
        "need": "  Tuiles déplacées après la tempête ",
        "language": "fr",
        "session_id": "session-1",
        "now": _MONDAY_EVENING,
    }
    values.update(overrides)
    return AiAssistantRequestService().capture(db, assistant=assistant, **values)


def test_capture_creates_a_request_owned_like_its_assistant(db: Session) -> None:
    assistant = _assistant(db)

    request, created = _capture(db, assistant)

    assert created
    assert (request.user_id, request.prospect_id, request.assistant_id) == (7, assistant.prospect_id, assistant.id)
    assert (request.name, request.contact, request.need) == (
        "Claire Martin",
        "06 12 34 56 78",
        "Tuiles déplacées après la tempête",
    )
    assert request.status == AiAssistantRequestStatus.NEW.value
    assert request.type == AiAssistantRequestType.OTHER.value
    assert request.received_outside_hours is True
    assert request.is_test is False


def test_the_same_session_updates_its_request_instead_of_creating_another(db: Session) -> None:
    assistant = _assistant(db)
    first, _ = _capture(db, assistant)

    second, created = _capture(db, assistant, contact="claire@example.fr", need="", now=_MONDAY_MORNING)

    assert not created
    assert second.id == first.id
    assert second.contact == "claire@example.fr"
    assert second.need == "Tuiles déplacées après la tempête"
    assert db.query(AiAssistantRequest).count() == 1


def test_requests_without_session_are_never_merged(db: Session) -> None:
    assistant = _assistant(db)

    _capture(db, assistant, session_id=None)
    _capture(db, assistant, session_id=None)

    assert db.query(AiAssistantRequest).count() == 2


def test_a_handled_or_stale_request_is_never_reopened_by_its_session(db: Session) -> None:
    assistant = _assistant(db)
    handled, _ = _capture(db, assistant)
    AiAssistantRequestService().update_for_owner(db, handled, status=AiAssistantRequestStatus.HANDLED)

    returning, created_after_handling = _capture(db, assistant, need="La gouttière fuit aussi")
    returning.created_at = datetime.utcnow() - timedelta(hours=25)
    db.commit()
    _, created_after_a_day = _capture(db, assistant)

    assert created_after_handling and created_after_a_day
    assert handled.need == "Tuiles déplacées après la tempête"
    assert handled.status == AiAssistantRequestStatus.HANDLED.value
    assert db.query(AiAssistantRequest).count() == 3


def test_the_pending_count_ignores_tests_and_deleted_assistants(db: Session) -> None:
    assistant = _assistant(db)
    service = AiAssistantRequestService()
    _capture(db, assistant, session_id="visitor")
    _capture(db, assistant, session_id="operator", is_test=True)

    assert service.pending_count(db, 7) == 1

    assistant.deleted_at = datetime.utcnow()
    db.commit()

    assert service.pending_count(db, 7) == 0
    assert service.list_for_owner(db, 7) == []


def test_opening_hours_decide_outside_hours_and_missing_hours_stay_unknown(db: Session) -> None:
    assistant = _assistant(db)
    during, _ = _capture(db, assistant, session_id="a", now=_MONDAY_MORNING)
    assistant.knowledge_json = {**(assistant.knowledge_json or {}), "opening_hours": []}
    db.commit()
    unknown, _ = _capture(db, assistant, session_id="b")

    assert during.received_outside_hours is False
    assert unknown.received_outside_hours is None


def test_the_request_links_the_session_conversation(db: Session) -> None:
    assistant = _assistant(db)
    ai_assistant_conversation_service.record_turn(
        db,
        assistant=assistant,
        session_id="session-1",
        language="fr",
        visitor_message="J'ai une fuite",
        reply="Je note, vos coordonnées ?",
    )

    request, _ = _capture(db, assistant)
    transcript = AiAssistantRequestService().transcript(db, request)

    assert request.conversation_id is not None
    assert [(line.role, line.content) for line in transcript] == [
        ("user", "J'ai une fuite"),
        ("assistant", "Je note, vos coordonnées ?"),
    ]


class _Recorder:
    """Collects the calls of a mocked async function."""

    def __init__(self, result: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = result

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> dict[str, _Recorder]:
    """Mock the model (a valid quote analysis), the summary email and the operator push."""
    model = _Recorder({"type": "quote", "summary": "Tuiles déplacées côté rue, devis demandé."})
    email = _Recorder({"success": True})
    push = _Recorder()
    monkeypatch.setattr(analyzer_module.llm_service, "complete_json", model)
    monkeypatch.setattr(email_sending_module.EmailSendingService, "send_via_user_identity", email)
    monkeypatch.setattr(request_module.notification_service, "notify_assistant_lead", push)
    return {"model": model, "email": email, "push": push}


def test_follow_up_types_summarizes_and_announces_a_sold_assistant_request_once(
    db: Session, outbox: dict[str, _Recorder]
) -> None:
    assistant = _assistant(db, status="delivered", email="patron@toitures-morel.fr")
    request, _ = _capture(db, assistant)
    service = AiAssistantRequestService()

    asyncio.run(service.follow_up(db, request, assistant))
    asyncio.run(service.follow_up(db, request, assistant))

    assert request.type == AiAssistantRequestType.QUOTE.value
    assert request.need_summary == "Tuiles déplacées côté rue, devis demandé."
    assert request.owner_notified_at is not None
    assert len(outbox["email"].calls) == 1
    sent = outbox["email"].calls[0]
    assert sent["recipient_email"] == "patron@toitures-morel.fr"
    assert sent["is_transactional"] is True
    assert "prospect_id" not in sent
    assert sent["subject"] == "Demande de devis — Claire Martin (hors horaires)"
    assert len(outbox["push"].calls) == 1
    assert outbox["push"].calls[0]["request_label"] == "Demande de devis"
    assert outbox["push"].calls[0]["received_outside_hours"] is True


def test_the_business_email_falls_back_on_the_prospect_address(db: Session, outbox: dict[str, _Recorder]) -> None:
    assistant = _assistant(db, status="delivered")
    request, _ = _capture(db, assistant)

    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    assert outbox["email"].calls[0]["recipient_email"] == "contact@toitures-morel.fr"


def test_a_demo_request_never_writes_to_the_prospect(db: Session, outbox: dict[str, _Recorder]) -> None:
    assistant = _assistant(db, status="active", email="patron@toitures-morel.fr")
    request, _ = _capture(db, assistant)

    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    assert outbox["email"].calls == []
    assert len(outbox["push"].calls) == 1


def test_an_internal_test_request_is_typed_but_never_announced(db: Session, outbox: dict[str, _Recorder]) -> None:
    assistant = _assistant(db, status="delivered", email="patron@toitures-morel.fr")
    request, _ = _capture(db, assistant, is_test=True)

    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    assert request.type == AiAssistantRequestType.QUOTE.value
    assert outbox["email"].calls == []
    assert outbox["push"].calls == []
    assert request.owner_notified_at is None


def test_counts_cover_7_and_30_days_and_the_known_outside_hours_share(db: Session) -> None:
    assistant = _assistant(db)
    now = datetime.utcnow()
    rows = [
        (now - timedelta(days=1), True, False),
        (now - timedelta(days=3), False, False),
        (now - timedelta(days=10), None, False),
        (now - timedelta(days=40), True, False),
        (now - timedelta(days=2), True, True),
    ]
    for index, (created_at, outside, is_test) in enumerate(rows):
        db.add(
            AiAssistantRequest(
                user_id=7,
                assistant_id=assistant.id,
                name=f"V{index}",
                contact="x",
                created_at=created_at,
                received_outside_hours=outside,
                is_test=is_test,
            )
        )
    db.commit()

    counts = AiAssistantRequestService().counts_for_assistants(db, [assistant.id, 999])

    assert (counts[assistant.id].last_7_days, counts[assistant.id].last_30_days) == (2, 3)
    assert counts[assistant.id].outside_hours_pct == 50
    assert counts[999].outside_hours_pct is None


def test_owner_updates_are_scoped_and_keep_handled_at_in_step(db: Session) -> None:
    assistant = _assistant(db)
    request, _ = _capture(db, assistant)
    service = AiAssistantRequestService()

    assert service.get_for_owner(db, 8, request.id) is None
    service.update_for_owner(db, request, status=AiAssistantRequestStatus.HANDLED, owner_note="  Rappelée  ")
    assert request.handled_at is not None
    assert request.owner_note == "Rappelée"
    assert service.pending_count(db, 7) == 0
    service.update_for_owner(db, request, status=AiAssistantRequestStatus.NEW)
    assert request.handled_at is None
    assert service.mark_handled(db, request) is True
    assert service.mark_handled(db, request) is False


def test_the_handled_link_only_confirms_on_open_and_acts_on_a_signed_post(db: Session) -> None:
    from api.v1.routes.ai_assistants import confirm_request_handled_page, mark_request_handled_from_email

    assistant = _assistant(db)
    request, _ = _capture(db, assistant)
    url = AiAssistantRequestLinks.handled_url(request.id)
    expires_at = int(url.split("exp=")[1].split("&")[0])
    token = url.split("token=")[1]

    opened = asyncio.run(confirm_request_handled_page(request.id, exp=expires_at, token=token, db=db))
    assert opened.status_code == 200
    assert '<form method="post"' in opened.body.decode()
    assert request.status == AiAssistantRequestStatus.NEW.value

    forged = asyncio.run(mark_request_handled_from_email(request.id, exp=expires_at, token="0" * 64, db=db))
    valid = asyncio.run(mark_request_handled_from_email(request.id, exp=expires_at, token=token, db=db))
    reopened = asyncio.run(confirm_request_handled_page(request.id, exp=expires_at, token=token, db=db))

    assert forged.status_code == 400
    assert valid.status_code == 200
    assert "marquée comme traitée" in valid.body.decode()
    assert request.status == AiAssistantRequestStatus.HANDLED.value
    assert "<form" not in reopened.body.decode()


def test_lost_announcements_are_picked_up_once_by_the_runner(
    engine, db: Session, outbox: dict[str, _Recorder], monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    now = datetime.utcnow()

    def add(minutes_ago: float, **fields: Any) -> AiAssistantRequest:
        request = AiAssistantRequest(
            user_id=7,
            assistant_id=assistant.id,
            name="Visiteur",
            contact="06 00 00 00 00",
            created_at=now - timedelta(minutes=minutes_ago),
            **fields,
        )
        db.add(request)
        db.commit()
        return request

    lost = add(10)
    add(10, status=AiAssistantRequestStatus.HANDLED.value)
    add(10, owner_notified_at=now)
    add(10, is_test=True)
    add(10, legacy_lead_id=1)
    add(0.5)
    add(60 * 25)
    monkeypatch.setattr(request_module, "SessionLocal", sessionmaker(bind=engine))
    service = AiAssistantRequestService()

    assert service.unannounced_request_ids(db, now=now) == [lost.id]
    assert asyncio.run(service.announce_pending()) == 1
    assert asyncio.run(service.announce_pending()) == 0
    assert len(outbox["push"].calls) == 1


def test_the_migration_copies_legacy_leads_once_as_handled_history(engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests_migration, "engine", engine)
    AiAssistantRequest.__table__.drop(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        AiAssistantLead(user_id=7, prospect_id=3, assistant_id=5, name="Marc", contact="marc@x.lu", need="Un devis")
    )
    session.commit()

    requests_migration.run_migration()
    requests_migration.run_migration()

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name, status, legacy_lead_id, need_summary FROM ai_assistant_requests")).all()
    assert [tuple(row) for row in rows] == [("Marc", "handled", 1, "Un devis")]


def test_the_summary_email_escapes_visitor_text_and_links_the_contact() -> None:
    rendered = AiAssistantRequestEmail.render(
        RequestEmailContent(
            business_name="Toitures Morel",
            assistant_name="Léa",
            request_type=AiAssistantRequestType.URGENT,
            visitor_name="<b>Claire</b>",
            contact="06 12 34 56 78",
            need="Fuite <script>",
            need_summary="Fuite sous la toiture.",
            received_at=datetime(2026, 9, 21, 21, 30),
            received_outside_hours=True,
            transcript=[TranscriptLine(role="user", content="Ça goutte <vite>")],
            handled_url="https://api.example/handled?exp=1&token=abc",
            photo_urls=("https://cdn.example/p1.jpg",),
        )
    )

    assert rendered.subject == "Urgence — <b>Claire</b> (hors horaires)"
    assert "&lt;b&gt;Claire&lt;/b&gt;" in rendered.html
    assert "<script>" not in rendered.html
    assert 'href="tel:0612345678"' in rendered.html
    assert "Reçue le 21/09/2026 à 21:30, en dehors de vos horaires" in rendered.html
    assert "Ça goutte &lt;vite&gt;" in rendered.html
    assert "https://api.example/handled?exp=1&amp;token=abc" in rendered.html
    assert "Photo 1" in rendered.html
