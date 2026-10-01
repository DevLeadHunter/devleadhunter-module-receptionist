"""
The client space home's live figures: the last 30 business days, in all and day by day.

The database is an in-memory SQLite; times are stored naive UTC and the days are Paris days.
"""

from datetime import datetime
from itertools import count
from typing import Any

from sqlalchemy.orm import Session

from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_message import AiAssistantMessage
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from models.user import User
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.client_space_activity import ACTIVITY_DAYS, AiAssistantClientActivity
from services.ai_assistant.client_space_example import ai_assistant_client_space_example

# Thursday 1 October 2026, 10:00 in Paris (UTC+2).
_NOW = datetime(2026, 10, 1, 8, 0)
_SESSIONS = count(1)


def _assistant(db: Session) -> AiAssistant:
    db.add(User(id=7, name="Dibodev", email="operateur@dibodev.fr", hashed_password="x"))
    prospect = ProspectDB(name="Toitures Morel", category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    return ai_assistant_service.create(
        db, user_id=7, business_name="Toitures Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )


def _conversation(
    db: Session, assistant: AiAssistant, *visitor_turns: datetime, is_test: bool = False, session_id: str = ""
) -> None:
    conversation = AiAssistantConversation(
        user_id=assistant.user_id,
        assistant_id=assistant.id,
        session_id=session_id or f"session-{next(_SESSIONS)}",
        language="fr",
        message_count=2 * len(visitor_turns),
        is_test=is_test,
        started_at=visitor_turns[0],
        last_message_at=visitor_turns[-1],
    )
    for moment in visitor_turns:
        conversation.messages.append(AiAssistantMessage(role="user", content="Bonjour ?", created_at=moment))
        conversation.messages.append(AiAssistantMessage(role="assistant", content="Bonjour !", created_at=moment))
    db.add(conversation)
    db.commit()


def _request(db: Session, assistant: AiAssistant, created_at: datetime, **fields: Any) -> None:
    values: dict[str, Any] = {
        "user_id": assistant.user_id,
        "assistant_id": assistant.id,
        "name": "Marc Dubois",
        "contact": "06 98 76 54 32",
        "type": "quote",
        "need": "Des tuiles ont bougé",
        "created_at": created_at,
        "received_outside_hours": False,
    }
    values.update(fields)
    db.add(AiAssistantRequest(**values))
    db.commit()


def test_the_chart_counts_each_paris_day_of_the_last_30_days_and_leaves_tests_out(db: Session) -> None:
    assistant = _assistant(db)
    # 23:30 UTC on 30/09 is already 1 October in Paris; the visitor writes again on the same Paris day.
    _conversation(db, assistant, datetime(2026, 9, 30, 23, 30), datetime(2026, 10, 1, 7, 0))
    # A returning visitor counts on each day they write.
    _conversation(db, assistant, datetime(2026, 9, 20, 9, 0), datetime(2026, 9, 29, 9, 0))
    _conversation(db, assistant, datetime(2026, 9, 29, 15, 0), is_test=True)
    # 1 September is out of the window, which opens on 2 September.
    _conversation(db, assistant, datetime(2026, 9, 1, 9, 0))
    _request(db, assistant, datetime(2026, 9, 29, 9, 5))
    _request(db, assistant, datetime(2026, 9, 29, 19, 0), received_outside_hours=True)
    _request(db, assistant, datetime(2026, 9, 29, 16, 0), is_test=True)
    _request(db, assistant, datetime(2026, 9, 1, 12, 0))

    days = AiAssistantClientActivity.by_day(db, assistant, now=_NOW)

    assert len(days) == ACTIVITY_DAYS and (days[0].day, days[-1].day) == ("2026-09-02", "2026-10-01")
    by_day = {entry.day: (entry.conversations, entry.requests) for entry in days}
    assert by_day["2026-10-01"] == (1, 0)
    assert by_day["2026-09-30"] == (0, 0)
    assert by_day["2026-09-29"] == (1, 2)
    assert by_day["2026-09-20"] == (1, 0)
    assert sum(conversations for conversations, _requests in by_day.values()) == 3


def test_the_figures_cover_the_same_30_days_as_the_chart(db: Session) -> None:
    assistant = _assistant(db)
    _conversation(db, assistant, datetime(2026, 9, 20, 9, 0), datetime(2026, 9, 29, 9, 0))
    _conversation(db, assistant, datetime(2026, 9, 1, 9, 0))
    _request(db, assistant, datetime(2026, 9, 29, 9, 5), outcome="won", status="handled")
    _request(db, assistant, datetime(2026, 9, 29, 19, 0), received_outside_hours=True)
    _request(db, assistant, datetime(2026, 9, 1, 12, 0))

    figures = AiAssistantClientActivity.recent_figures(db, assistant, now=_NOW)

    assert (figures.days, figures.conversations, figures.requests, figures.quotes, figures.won) == (30, 1, 2, 2, 1)
    assert figures.outside_hours_pct == 50


def test_the_example_space_has_a_month_of_activity_ending_today() -> None:
    space = ai_assistant_client_space_example.build(now=datetime(2026, 10, 1, 10, 0))

    assert space.recent is not None and len(space.activity) == ACTIVITY_DAYS
    assert space.activity[-1].day == "2026-10-01"
    assert space.recent.requests == sum(day.requests for day in space.activity)
    assert space.recent.conversations == sum(day.conversations for day in space.activity)


def test_a_demo_space_counts_the_visitor_own_sessions_only_their_tests_included(db: Session) -> None:
    assistant = _assistant(db)
    _conversation(db, assistant, datetime(2026, 9, 29, 9, 0), session_id="visitor-session-1")
    _conversation(db, assistant, datetime(2026, 9, 30, 9, 0), is_test=True, session_id="visitor-session-2")
    _conversation(db, assistant, datetime(2026, 9, 30, 10, 0), session_id="someone-else-session")
    _request(db, assistant, datetime(2026, 9, 29, 9, 5), session_id="visitor-session-1", received_outside_hours=True)
    _request(db, assistant, datetime(2026, 9, 30, 10, 5), session_id="someone-else-session")
    sessions = ["visitor-session-1", "visitor-session-2"]

    figures = AiAssistantClientActivity.session_figures(db, assistant, sessions, now=_NOW)
    by_day = {
        entry.day: (entry.conversations, entry.requests)
        for entry in AiAssistantClientActivity.by_day(db, assistant, session_ids=sessions, now=_NOW)
    }

    assert (figures.conversations, figures.requests, figures.outside_hours_pct) == (2, 1, 100)
    assert by_day["2026-09-29"] == (1, 1) and by_day["2026-09-30"] == (1, 0)
    assert AiAssistantClientActivity.session_figures(db, assistant, [], now=_NOW).conversations == 0
