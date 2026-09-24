"""Every chat turn is journaled per widget session; the owner reads the latest ones and old ones are purged."""

import importlib
import pkgutil
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import models
from core.database import Base
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_message import AiAssistantMessage
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.conversation_service import (
    MAX_STORED_MESSAGE_CHARS,
    RECENT_CONVERSATIONS_LIMIT,
    RETENTION_DAYS,
    ai_assistant_conversation_service,
)

# Load every model so SQLAlchemy can configure the mappers (relationships resolve across models).
for _module in pkgutil.iter_modules(models.__path__):
    importlib.import_module("models." + _module.name)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _assistant(db: Session, *, prospect_id: int = 42) -> AiAssistant:
    return ai_assistant_service.create(
        db, user_id=1, business_name="Cabinet Meyer", prospect_id=prospect_id, country="FR", use_brand_color=False
    )


def test_record_turn_journals_the_visitor_and_the_reply_per_session(db) -> None:
    """Turns of one session land in one conversation; a second session opens another one."""
    assistant = _assistant(db)
    first = ai_assistant_conversation_service.record_turn(
        db, assistant=assistant, session_id="s1", language="fr", visitor_message="  Vous êtes ouverts ?  ", reply="Oui."
    )
    again = ai_assistant_conversation_service.record_turn(
        db, assistant=assistant, session_id="s1", language="fr", visitor_message="Et demain ?", reply="Aussi."
    )
    other = ai_assistant_conversation_service.record_turn(
        db, assistant=assistant, session_id="s2", language="de", visitor_message="Hallo", reply="Hallo!"
    )

    assert again.id == first.id
    assert other.id != first.id
    assert first.message_count == 4
    assert [message.role for message in first.messages] == ["user", "assistant", "user", "assistant"]
    assert first.messages[0].content == "Vous êtes ouverts ?"
    assert first.user_id == 1 and first.prospect_id == 42 and first.language == "fr"
    assert other.language == "de"


def test_record_turn_bounds_the_stored_content_and_survives_a_missing_session(db) -> None:
    """A huge message is cut to the stored bound; without a session id the turn still lands somewhere."""
    assistant = _assistant(db)
    conversation = ai_assistant_conversation_service.record_turn(
        db, assistant=assistant, session_id=None, language=None, visitor_message="x" * 5000, reply="ok"
    )
    assert len(conversation.messages[0].content) == MAX_STORED_MESSAGE_CHARS
    assert conversation.session_id


def test_counts_for_assistants_split_the_last_7_and_30_days(db) -> None:
    """Counts follow the conversation start: one this week, one three weeks ago, one too old to count."""
    assistant = _assistant(db)
    now = datetime.now(UTC).replace(tzinfo=None)
    for session, started_days_ago in (("recent", 1), ("older", 20), ("ancient", 45)):
        conversation = ai_assistant_conversation_service.record_turn(
            db, assistant=assistant, session_id=session, language="fr", visitor_message="?", reply="!"
        )
        conversation.started_at = now - timedelta(days=started_days_ago)
    db.commit()

    counts = ai_assistant_conversation_service.counts_for_assistants(db, [assistant.id, 999])
    assert counts[assistant.id].last_7_days == 1
    assert counts[assistant.id].last_30_days == 2
    assert counts[999].last_7_days == 0 and counts[999].last_30_days == 0
    assert ai_assistant_conversation_service.counts_for_assistants(db, []) == {}


def test_recent_for_assistant_is_newest_first_and_bounded(db) -> None:
    """The journal shows the latest conversations first, capped to the drawer's page."""
    assistant = _assistant(db)
    for index in range(RECENT_CONVERSATIONS_LIMIT + 5):
        ai_assistant_conversation_service.record_turn(
            db, assistant=assistant, session_id=f"s{index}", language="fr", visitor_message=f"q{index}", reply="r"
        )

    recent = ai_assistant_conversation_service.recent_for_assistant(db, assistant.id)
    assert len(recent) == RECENT_CONVERSATIONS_LIMIT
    assert recent[0].session_id == f"s{RECENT_CONVERSATIONS_LIMIT + 4}"
    assert recent[0].messages[0].content == f"q{RECENT_CONVERSATIONS_LIMIT + 4}"


def test_purge_old_deletes_quiet_conversations_with_their_messages(db) -> None:
    """A conversation quiet for longer than the retention goes, messages included; a live one stays."""
    assistant = _assistant(db)
    stale = ai_assistant_conversation_service.record_turn(
        db, assistant=assistant, session_id="stale", language="fr", visitor_message="a", reply="b"
    )
    stale.last_message_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=RETENTION_DAYS + 1)
    ai_assistant_conversation_service.record_turn(
        db, assistant=assistant, session_id="live", language="fr", visitor_message="c", reply="d"
    )
    db.commit()

    assert ai_assistant_conversation_service.purge_old(db) == 1
    assert db.query(AiAssistantConversation).count() == 1
    assert db.query(AiAssistantMessage).count() == 2
