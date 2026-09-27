"""
The Monday email of the questions a sold assistant could not answer: once a week, only with new questions, only
for a sold business; and the count of those questions on the owner's list.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import services.email_sending_service as email_sending_module
from api.v1.routes.ai_assistants import _to_owner_response
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from models.user import User
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.faq_service import ai_assistant_faq_service
from services.ai_assistant.unanswered_digest import AiAssistantUnansweredDigest, ai_assistant_unanswered_digest
from tests.assistant_fakes import AsyncCallRecorder

# Monday 28 September 2026, 08:30 in Paris (06:30 UTC): the digest hour.
MONDAY_MORNING = datetime(2026, 9, 28, 6, 30)
TUESDAY_MORNING = datetime(2026, 9, 29, 6, 30)


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=engine)()
    session.add(User(id=7, name="Dibodev", email="operateur@dibodev.fr", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> AsyncCallRecorder:
    """Mock the email sender."""
    email = AsyncCallRecorder({"success": True})
    monkeypatch.setattr(email_sending_module.EmailSendingService, "send_via_user_identity", email)
    return email


def _assistant(
    db: Session, *, status: str = "delivered", email: str | None = "patron@toitures-morel.fr"
) -> AiAssistant:
    prospect = ProspectDB(name="Toitures Morel", category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Toitures Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = status
    assistant.email = email
    db.commit()
    return assistant


def _with_unanswered(db: Session, assistant: AiAssistant, entries: list[dict[str, Any]]) -> None:
    knowledge = dict(assistant.knowledge_json or {})
    knowledge["unanswered"] = entries
    assistant.knowledge_json = knowledge
    db.commit()
    db.refresh(assistant)


def _entry(question: str, *, count: int, last_seen: datetime) -> dict[str, Any]:
    return {
        "question": question,
        "count": count,
        "first_seen": (last_seen - timedelta(days=1)).isoformat(),
        "last_seen": last_seen.isoformat(),
    }


def test_the_week_key_and_the_sending_window() -> None:
    assert AiAssistantUnansweredDigest.week_key(datetime(2026, 9, 28, 8, 30)) == "2026-W40"
    assert AiAssistantUnansweredDigest.is_due_moment(datetime(2026, 9, 28, 8, 0))
    assert not AiAssistantUnansweredDigest.is_due_moment(datetime(2026, 9, 28, 7, 59))
    assert not AiAssistantUnansweredDigest.is_due_moment(datetime(2026, 9, 29, 9, 0))


def test_the_monday_digest_lists_the_week_questions_once(db: Session, outbox: AsyncCallRecorder) -> None:
    assistant = _assistant(db)
    _with_unanswered(
        db,
        assistant,
        [
            _entry("Faites-vous le nettoyage des gouttières ?", count=3, last_seen=MONDAY_MORNING - timedelta(days=2)),
            _entry("Intervenez-vous le samedi ?", count=1, last_seen=MONDAY_MORNING - timedelta(days=5)),
            _entry("Posez-vous des velux ?", count=9, last_seen=MONDAY_MORNING - timedelta(days=20)),
        ],
    )

    sent = asyncio.run(ai_assistant_unanswered_digest.send_due(db, now=MONDAY_MORNING))
    again = asyncio.run(ai_assistant_unanswered_digest.send_due(db, now=MONDAY_MORNING + timedelta(hours=3)))

    assert (sent, again) == (1, 0)
    [email] = outbox.calls
    assert email["recipient_email"] == "patron@toitures-morel.fr"
    assert email["subject"] == f"2 questions que {assistant.assistant_name} n'a pas su répondre cette semaine"
    body = email["body_html"]
    assert "Faites-vous le nettoyage des gouttières ?" in body and "(posée 3 fois)" in body
    assert "Intervenez-vous le samedi ?" in body
    # A question last asked three weeks ago is not this week's.
    assert "velux" not in body
    assert "/client/" in body and "Répondre depuis mon espace" in body
    assert ai_assistant_faq_service.unanswered_digest_week(assistant) == "2026-W40"


def test_no_digest_outside_monday_morning_nor_without_new_questions(db: Session, outbox: AsyncCallRecorder) -> None:
    assistant = _assistant(db)
    _with_unanswered(db, assistant, [_entry("Vos tarifs ?", count=2, last_seen=MONDAY_MORNING - timedelta(days=1))])
    quiet = _assistant(db)
    _with_unanswered(db, quiet, [_entry("Vos tarifs ?", count=2, last_seen=MONDAY_MORNING - timedelta(days=12))])

    on_tuesday = asyncio.run(ai_assistant_unanswered_digest.send_due(db, now=TUESDAY_MORNING))
    on_monday = asyncio.run(ai_assistant_unanswered_digest.send_due(db, now=MONDAY_MORNING))

    assert (on_tuesday, on_monday) == (0, 1)
    # Tuesday marks nothing; Monday marks the quiet one too, so it is not scanned again this week.
    assert ai_assistant_faq_service.unanswered_digest_week(quiet) == "2026-W40"
    assert len(outbox.calls) == 1


def test_a_demo_or_an_addressless_business_gets_no_digest(db: Session, outbox: AsyncCallRecorder) -> None:
    demo = _assistant(db, status="active")
    silent = _assistant(db, email=None)
    for assistant in (demo, silent):
        _with_unanswered(db, assistant, [_entry("Vos tarifs ?", count=1, last_seen=MONDAY_MORNING - timedelta(days=1))])
    silent_prospect = db.get(ProspectDB, silent.prospect_id)
    assert silent_prospect is not None and not silent_prospect.email

    assert asyncio.run(ai_assistant_unanswered_digest.send_due(db, now=MONDAY_MORNING)) == 0
    assert outbox.calls == []


def test_the_owner_list_counts_the_questions_waiting_for_an_answer(db: Session) -> None:
    assistant = _assistant(db)
    _with_unanswered(
        db,
        assistant,
        [
            _entry("Vos tarifs ?", count=2, last_seen=MONDAY_MORNING),
            _entry("Vous vous déplacez ?", count=1, last_seen=MONDAY_MORNING),
        ],
    )

    assert _to_owner_response(assistant).unanswered_count == 2
    assert _to_owner_response(_assistant(db)).unanswered_count == 0
