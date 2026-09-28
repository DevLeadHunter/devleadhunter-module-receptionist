"""
The daily cap of visitor messages per assistant: counted from the journal over the business day (Paris), the test
visits apart; past it, a fixed reply without the model, the contact form offered, and the operator told once a day.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import api.v1.routes.ai_assistant_widget as routes
import migrations.add_ai_assistant_message_cap_alerted_on as alert_column_migration
import services.ai_assistant.daily_message_cap as cap_module
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_message import AiAssistantMessage
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from schemas.ai_assistant import AiAssistantChatMessage, AiAssistantChatRequest
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.chat_service import ChatAnswer
from services.ai_assistant.daily_message_cap import ai_assistant_daily_message_cap
from services.rate_limiter import SlidingWindowRateLimiter
from tests.assistant_fakes import VISITOR_REQUEST, AsyncCallRecorder

_PARIS = ZoneInfo("Europe/Paris")
# Tuesday 29 September 2026, 10:00 in Paris (summer time: UTC+2).
_TUESDAY_MORNING = datetime(2026, 9, 29, 10, 0, tzinfo=_PARIS)


@pytest.fixture
def capped_routes(monkeypatch: pytest.MonkeyPatch) -> dict[str, AsyncCallRecorder]:
    """A cap of two messages a day, fresh rate limits, the model and the operator's alert recorded."""
    model = AsyncCallRecorder(result=ChatAnswer(reply="Du lundi au vendredi."))
    alert = AsyncCallRecorder()
    monkeypatch.setattr(cap_module.settings, "assistant_daily_visitor_message_cap", 2)
    monkeypatch.setattr(routes, "assistant_chat_limiter", SlidingWindowRateLimiter(30, 300))
    monkeypatch.setattr(routes.ai_assistant_chat_service, "answer", model)
    monkeypatch.setattr(routes.ai_assistant_request_follow_up, "schedule_follow_up", lambda request_id: None)
    monkeypatch.setattr(cap_module.notification_service, "notify_assistant_daily_cap_reached", alert)
    return {"model": model, "alert": alert}


def _assistant(db: Session, business_name: str = "Toitures Morel - Couvreur à Rennes") -> AiAssistant:
    prospect = ProspectDB(name="Toitures Morel", category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name=business_name, prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = "delivered"
    assistant.assistant_name = "Sofia"
    db.commit()
    return assistant


def _visitor_message(
    db: Session, assistant: AiAssistant, *, at_utc: datetime, session_id: str = "s1", is_test: bool = False
) -> None:
    conversation = (
        db.query(AiAssistantConversation).filter(AiAssistantConversation.session_id == session_id).one_or_none()
    )
    if conversation is None:
        conversation = AiAssistantConversation(
            user_id=7, assistant_id=assistant.id, session_id=session_id, message_count=0, is_test=is_test or None
        )
        db.add(conversation)
    conversation.last_message_at = max(conversation.last_message_at or at_utc, at_utc)
    conversation.messages.append(AiAssistantMessage(role="user", content="?", created_at=at_utc))
    conversation.messages.append(AiAssistantMessage(role="assistant", content="!", created_at=at_utc))
    db.commit()


def _chat(db: Session, assistant: AiAssistant, content: str = "Vous ouvrez le samedi ?", **fields: Any) -> Any:
    payload = AiAssistantChatRequest(
        messages=[AiAssistantChatMessage(role="user", content=content)], session_id="s1", language="fr", **fields
    )
    return asyncio.run(routes.chat_with_assistant(assistant.slug, payload, VISITOR_REQUEST, db))


def test_the_day_counts_from_midnight_in_paris_and_test_visits_apart(db: Session) -> None:
    assistant = _assistant(db)
    # 23:30 in Paris on Monday is 21:30 UTC; 00:30 on Tuesday is 22:30 UTC, still Monday in UTC.
    _visitor_message(db, assistant, at_utc=datetime(2026, 9, 28, 21, 30), session_id="late")
    _visitor_message(db, assistant, at_utc=datetime(2026, 9, 28, 22, 30), session_id="night")
    _visitor_message(db, assistant, at_utc=datetime(2026, 9, 29, 7, 0), session_id="morning")
    _visitor_message(db, assistant, at_utc=datetime(2026, 9, 29, 7, 30), session_id="operator", is_test=True)

    count = ai_assistant_daily_message_cap.visitor_messages_today

    assert count(db, assistant.id, is_test=False, local_now=_TUESDAY_MORNING) == 2
    assert count(db, assistant.id, is_test=True, local_now=_TUESDAY_MORNING) == 1
    assert ai_assistant_daily_message_cap.day_start(_TUESDAY_MORNING) == datetime(2026, 9, 28, 22, 0)


def test_past_the_cap_the_chat_answers_without_the_model_and_offers_the_form(
    db: Session, capped_routes: dict[str, AsyncCallRecorder]
) -> None:
    assistant = _assistant(db)

    answered = [_chat(db, assistant) for _ in range(2)]
    capped = _chat(db, assistant)
    again = _chat(db, assistant, "Et le dimanche ?")

    assert [reply.daily_limit_reached for reply in answered] == [False, False]
    assert len(capped_routes["model"].calls) == 2
    assert capped.daily_limit_reached is True and again.daily_limit_reached is True
    assert capped.reply == (
        "Sofia ne peut plus répondre aujourd'hui : laissez votre numéro, Toitures Morel vous rappelle."
    )
    # The capped turns stay in the journal: the owner sees what visitors asked meanwhile.
    [conversation] = db.query(AiAssistantConversation).all()
    assert conversation.message_count == 8
    # The operator is told once a day, whatever the number of capped turns.
    [alert] = capped_routes["alert"].calls
    assert (alert["user_id"], alert["cap"]) == (7, 2)


def test_a_capped_turn_still_files_the_contact_the_visitor_leaves(
    db: Session, capped_routes: dict[str, AsyncCallRecorder]
) -> None:
    assistant = _assistant(db)
    for _ in range(2):
        _chat(db, assistant)

    capped = _chat(db, assistant, "D'accord, mon numéro : 06 12 34 56 78", visitor_name="Julie")

    assert capped.daily_limit_reached is True
    assert capped.captured_contact is not None and capped.captured_contact.contact == "06 12 34 56 78"
    assert db.query(AiAssistantRequest).one().name == "Julie"


def test_a_contact_filed_past_the_cap_schedules_no_follow_up(
    db: Session, capped_routes: dict[str, AsyncCallRecorder], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past the cap the request is filed, and its follow-up (a model call) is not scheduled."""
    follow_ups: list[int] = []
    monkeypatch.setattr(routes.ai_assistant_request_follow_up, "schedule_follow_up", follow_ups.append)
    assistant = _assistant(db)
    for _ in range(2):
        _chat(db, assistant)

    capped = _chat(db, assistant, "Rappelez-moi au 06 12 34 56 78")

    assert capped.daily_limit_reached is True
    assert db.query(AiAssistantRequest).one().contact == "06 12 34 56 78"
    assert follow_ups == []


def test_the_operator_tests_use_their_own_budget_and_never_raise_the_alert(
    db: Session, capped_routes: dict[str, AsyncCallRecorder]
) -> None:
    assistant = _assistant(db)

    tests = [_chat(db, assistant, internal=True) for _ in range(3)]
    visitor = _chat(db, assistant)

    assert [reply.daily_limit_reached for reply in tests] == [False, False, True]
    assert visitor.daily_limit_reached is False
    assert capped_routes["alert"].calls == []


def test_the_stream_of_a_capped_turn_is_its_closing_event_alone(
    db: Session, capped_routes: dict[str, AsyncCallRecorder], monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    monkeypatch.setattr(routes, "SessionLocal", sessionmaker(bind=db.get_bind()))
    for _ in range(2):
        _chat(db, assistant)
    payload = AiAssistantChatRequest(
        messages=[AiAssistantChatMessage(role="user", content="Encore une question")], session_id="s1", language="en"
    )

    async def frames() -> list[str]:
        response = await routes.stream_chat_with_assistant(assistant.slug, payload, VISITOR_REQUEST, db)
        return [chunk if isinstance(chunk, str) else chunk.decode() async for chunk in response.body_iterator]

    [closing] = asyncio.run(frames())

    assert json.loads(closing[len("data: ") :]) == {
        "done": True,
        "reply": "Sofia can't answer any more today: leave your number and Toitures Morel will call you back.",
        "offer_booking": False,
        "follow_ups": [],
        "daily_limit_reached": True,
        "captured_contact": None,
    }


def test_the_alert_is_claimed_once_a_business_day(db: Session, capped_routes: dict[str, AsyncCallRecorder]) -> None:
    assistant = _assistant(db)
    wednesday = datetime(2026, 9, 30, 9, 0, tzinfo=_PARIS)

    sent = [
        asyncio.run(ai_assistant_daily_message_cap.alert_operator_once(db, assistant, local_now=moment))
        for moment in (_TUESDAY_MORNING, _TUESDAY_MORNING, wednesday)
    ]

    assert sent == [True, False, True]
    assert len(capped_routes["alert"].calls) == 2
    db.refresh(assistant)
    assert assistant.message_cap_alerted_on == wednesday.date()


def test_the_capped_reply_speaks_the_widget_language() -> None:
    assistant = AiAssistant(business_name="Garage Martin", assistant_name="Hugo")

    reply = ai_assistant_daily_message_cap.capped_reply

    assert reply(assistant, "lb").startswith("Hugo kann haut net méi äntweren")
    assert reply(assistant, "lu") == reply(assistant, "lb")
    assert reply(assistant, "de").endswith("Garage Martin ruft Sie zurück.")
    assert reply(assistant, "it") == reply(assistant, None) == reply(assistant, "fr")


def test_the_migration_adds_the_alert_column_once(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE ai_assistants (id INTEGER PRIMARY KEY, slug VARCHAR(120))"))
        conn.commit()
    monkeypatch.setattr(alert_column_migration, "engine", engine)

    alert_column_migration.run_migration()
    alert_column_migration.run_migration()

    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistants")}
    assert "message_cap_alerted_on" in columns
