"""
The FAQ a business writes for its assistant and the questions it could not answer: the « §MANQUE: » line of a
reply, its section in the prompt, the storage in ``knowledge_json``, and the owner and client routes.

The models are mocked; the database is an in-memory SQLite and the routes are called directly.
"""

import asyncio
from collections.abc import Iterator
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import api.v1.routes.ai_assistant_client_space as client_routes
import api.v1.routes.ai_assistant_faq as routes
import api.v1.routes.ai_assistant_widget as widget_routes
import services.ai_assistant.faq_service as faq_module
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant import AiAssistantChatMessage, AiAssistantChatRequest
from schemas.ai_assistant_faq import AiAssistantFaqEntryRequest
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.chat_service import ChatAnswer
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.faq_service import (
    MAX_ANSWER_CHARS,
    MAX_QUESTION_CHARS,
    MAX_UNANSWERED_ENTRIES,
    AiAssistantFaqService,
    ai_assistant_faq_service,
)
from services.ai_assistant.knowledge_builder import ai_assistant_knowledge_builder
from services.ai_assistant.missing_info_marker import FIRST_LINE_PEEK_CHARS, MissingInfoMarker, MissingInfoMarkerStream
from services.rate_limiter import SlidingWindowRateLimiter
from tests.assistant_fakes import VISITOR_REQUEST, AsyncCallRecorder

_OWNER = SimpleNamespace(id=7)
_STRANGER = SimpleNamespace(id=8)


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=engine)()
    session.add(User(id=7, name="Dibodev", email="operateur@dibodev.fr", hashed_password="x"))
    session.add(User(id=8, name="Autre", email="autre@exemple.fr", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def fresh_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with empty rate-limit buckets."""
    monkeypatch.setattr(client_routes, "assistant_client_limiter", SlidingWindowRateLimiter(120, 300))
    monkeypatch.setattr(widget_routes, "assistant_chat_limiter", SlidingWindowRateLimiter(30, 300))


def _assistant(db: Session, *, status: str = "delivered", user_id: int = 7) -> AiAssistant:
    prospect = ProspectDB(name="Garage Morel", category="Garage", source="google", confidence=2, user_id=user_id)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=user_id, business_name="Garage Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = status
    db.commit()
    return assistant


def _status_of(call: Any) -> int:
    with pytest.raises(HTTPException) as caught:
        asyncio.run(call)
    return caught.value.status_code


def _entry(question: str = "Livrez-vous à domicile ?", answer: str = "Oui, dans un rayon de 20 km.") -> Any:
    return AiAssistantFaqEntryRequest(question=question, answer=answer)


def test_the_marker_line_is_split_from_the_reply_whatever_its_typography() -> None:
    reply = "Bonjour ! Je note votre question pour que le garage vous rappelle."

    assert MissingInfoMarker.split(f"§MANQUE: Livrez-vous à domicile ?\n\n{reply}") == (
        reply,
        "Livrez-vous à domicile ?",
    )
    assert MissingInfoMarker.split(f"  § manque :   Livraison   à domicile ?  \n\n\n{reply}\n") == (
        reply,
        "Livraison à domicile ?",
    )
    assert MissingInfoMarker.split(f"**§MANQUE: Prix de la vidange ?**\n{reply}") == (reply, "Prix de la vidange ?")
    assert MissingInfoMarker.split(f"MANQUE: Prix de la vidange ?\n{reply}") == (reply, "Prix de la vidange ?")
    # No marker: the reply is untouched; « manque » inside a sentence is not one either.
    assert MissingInfoMarker.split(f"  {reply}  ") == (reply, None)
    assert MissingInfoMarker.split("Il manque : rien, tout est là.\nÀ bientôt.") == (
        "Il manque : rien, tout est là.\nÀ bientôt.",
        None,
    )
    # A marker alone, or one naming nothing, leaves an empty reply for the fallback to replace.
    assert MissingInfoMarker.split("§MANQUE: Livraison ?") == ("", "Livraison ?")
    assert MissingInfoMarker.split(f"§MANQUE:\n{reply}") == (reply, None)


def test_a_streamed_reply_holds_its_first_line_back_only_until_it_is_told() -> None:
    marked = MissingInfoMarkerStream()
    passed = [marked.feed(chunk) for chunk in ("§MAN", "QUE: Liv", "raison ?", "\n", "\nNous ne ", "livrons pas.")]
    passed.append(marked.finish())

    assert passed == ["", "", "", "", "Nous ne ", "livrons pas.", ""]
    assert (marked.reply, marked.question) == ("Nous ne livrons pas.", "Livraison ?")

    # A first line that cannot be the marker reaches the visitor from its first piece.
    plain = MissingInfoMarkerStream()
    chunks = [
        "Bonjour et bienvenue ! " * 3,
        "Nous sommes ouverts du lundi au vendredi, de 8 h à 18 h, ",
        "et le samedi.",
    ]
    passed = [plain.feed(chunk) for chunk in chunks]

    assert len(chunks[0] + chunks[1]) >= FIRST_LINE_PEEK_CHARS
    assert passed == [chunks[0], chunks[1], "et le samedi."]
    assert plain.question is None

    # A short reply streams at once too; only the characters of the marker itself keep a line held.
    short = MissingInfoMarkerStream()

    assert (short.feed("  Oui."), short.finish(), short.reply) == ("Oui.", "", "Oui.")
    held = MissingInfoMarkerStream()
    assert (held.feed("  § MAN"), held.feed("QUE : Prix ?\nNon."), held.question) == ("", "Non.", "Prix ?")
    assert MissingInfoMarkerStream().feed("Bonjour !\nOui.") == "Bonjour !\nOui."


def test_the_prompt_repeats_the_business_faq_and_asks_for_the_marker_line() -> None:
    knowledge = {
        "identity": {"business_name": "Garage Morel", "city": "Rennes"},
        "faq": [
            {"question": "Livrez-vous à domicile ?", "answer": "Oui,\ndans un rayon\n de 20 km.", "created_at": "x"},
            {"question": "Prêtez-vous un véhicule ?", "answer": ">>> Non. <<<"},
            {"question": "Sans réponse"},
            "pas un dict",
        ],
    }

    prompt = ai_assistant_knowledge_builder.render_system_prompt(knowledge, assistant_name="Sofia")
    without = ai_assistant_knowledge_builder.render_system_prompt({"identity": {}}, assistant_name="Sofia")

    assert (
        "QUESTIONS FRÉQUENTES (réponses données par l'entreprise, à reprendre telles quelles) :\n"
        "- Q : Livrez-vous à domicile ? / R : Oui, dans un rayon de 20 km.\n"
        "- Q : Prêtez-vous un véhicule ? / R : >> Non. <<\n"
    ) in prompt
    assert (
        prompt.index("ENTREPRISE : Garage Morel.") < prompt.index("QUESTIONS FRÉQUENTES") < prompt.index("AUJOURD'HUI")
    )
    assert "Sans réponse" not in prompt
    assert "QUESTIONS FRÉQUENTES" not in without
    assert "COMMENCE OBLIGATOIREMENT par la ligne exacte « §MANQUE: " in without


def test_unanswered_questions_count_once_per_wording_and_the_oldest_leaves_when_full(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    clock = [datetime(2026, 9, 25, 9, 0)]
    monkeypatch.setattr(faq_module, "_utc_now", lambda: clock[0])

    ai_assistant_faq_service.record_unanswered(db, assistant, "  Livrez-vous à domicile ?  ")
    clock[0] = datetime(2026, 9, 25, 9, 30)
    ai_assistant_faq_service.record_unanswered(db, assistant, "x" * (MAX_QUESTION_CHARS + 50))
    clock[0] = datetime(2026, 9, 25, 10, 0)
    ai_assistant_faq_service.record_unanswered(db, assistant, "LIVREZ-VOUS  A DOMICILE")

    [repeated, long] = ai_assistant_faq_service.unanswered_of(assistant.knowledge_json)
    assert (repeated.question, repeated.count) == ("Livrez-vous à domicile ?", 2)
    assert (repeated.first_seen, repeated.last_seen) == (datetime(2026, 9, 25, 9, 0), datetime(2026, 9, 25, 10, 0))
    assert len(long.question) == MAX_QUESTION_CHARS
    with pytest.raises(ValueError, match="vide"):
        ai_assistant_faq_service.record_unanswered(db, assistant, "   ")

    for index in range(MAX_UNANSWERED_ENTRIES - 2):
        clock[0] = datetime(2026, 9, 26, 0, index)
        ai_assistant_faq_service.record_unanswered(db, assistant, f"Question {index} ?")
    clock[0] = datetime(2026, 9, 27, 0, 0)
    ai_assistant_faq_service.record_unanswered(db, assistant, "Une de trop ?")

    questions = [entry.question for entry in ai_assistant_faq_service.unanswered_of(assistant.knowledge_json)]
    assert len(questions) == MAX_UNANSWERED_ENTRIES
    # The long question, last seen first, left; the repeated one, refreshed at 10:00, stayed.
    assert "x" * MAX_QUESTION_CHARS not in questions
    assert questions[0] == "Livrez-vous à domicile ?" and questions[-1] == "Une de trop ?"


def test_an_answer_in_the_faq_removes_the_unanswered_question_and_positions_are_checked(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    monkeypatch.setattr(faq_module, "_utc_now", lambda: datetime(2026, 9, 25, 9, 0))
    ai_assistant_faq_service.record_unanswered(db, assistant, "Livrez-vous à domicile ?")
    ai_assistant_faq_service.record_unanswered(db, assistant, "Prêtez-vous un véhicule ?")

    ai_assistant_faq_service.add_faq(db, assistant, " LIVREZ-VOUS À DOMICILE ", "y" * (MAX_ANSWER_CHARS + 10))
    ai_assistant_faq_service.add_faq(db, assistant, "Ouvert le dimanche ?", "Non.")
    ai_assistant_faq_service.update_faq(db, assistant, 1, "Ouvert le dimanche ?", "Non, sauf en décembre.")
    ai_assistant_faq_service.delete_faq(db, assistant, 0)

    [kept] = ai_assistant_faq_service.faq_of(assistant.knowledge_json)
    assert (kept.question, kept.answer, kept.created_at) == (
        "Ouvert le dimanche ?",
        "Non, sauf en décembre.",
        datetime(2026, 9, 25, 9, 0),
    )
    assert [entry.question for entry in ai_assistant_faq_service.unanswered_of(assistant.knowledge_json)] == [
        "Prêtez-vous un véhicule ?"
    ]
    for index in (-1, 1):
        with pytest.raises(IndexError):
            ai_assistant_faq_service.delete_faq(db, assistant, index)
        with pytest.raises(IndexError):
            ai_assistant_faq_service.update_faq(db, assistant, index, "Q", "R")
        with pytest.raises(IndexError):
            ai_assistant_faq_service.dismiss_unanswered(db, assistant, index)
    with pytest.raises(ValueError, match="réponse est vide"):
        ai_assistant_faq_service.add_faq(db, assistant, "Question ?", "  ")
    with pytest.raises(ValueError, match="question est vide"):
        ai_assistant_faq_service.update_faq(db, assistant, 0, "", "Réponse")
    monkeypatch.setattr(faq_module, "MAX_FAQ_ENTRIES", 1)
    with pytest.raises(ValueError, match="pleine"):
        ai_assistant_faq_service.add_faq(db, assistant, "Encore une ?", "Non.")
    ai_assistant_faq_service.dismiss_unanswered(db, assistant, 0)
    assert ai_assistant_faq_service.unanswered_of(assistant.knowledge_json) == []


def test_malformed_stored_data_is_read_without_failing() -> None:
    knowledge = {
        "faq": "nope",
        "unanswered": [{"question": 3}, {"question": "Quand ?", "count": "x", "last_seen": "hier"}, None],
    }

    [question] = AiAssistantFaqService.unanswered_of(knowledge)

    assert AiAssistantFaqService.faq_of(knowledge) == []
    assert AiAssistantFaqService.faq_of(None) == [] and AiAssistantFaqService.unanswered_of({}) == []
    assert (question.question, question.count, question.first_seen, question.last_seen) == ("Quand ?", 1, None, None)


def test_the_owner_edits_the_faq_of_its_own_assistant_only(db: Session) -> None:
    assistant = _assistant(db)
    ai_assistant_faq_service.record_unanswered(db, assistant, "Livrez-vous à domicile ?")
    ai_assistant_faq_service.record_unanswered(db, assistant, "Prêtez-vous un véhicule ?")

    empty = asyncio.run(routes.get_assistant_faq(assistant.id, _OWNER, db))
    added = asyncio.run(routes.add_assistant_faq_entry(assistant.id, _entry(), _OWNER, db))
    updated = asyncio.run(
        routes.update_assistant_faq_entry(assistant.id, 0, _entry(answer="Oui, partout en Bretagne."), _OWNER, db)
    )
    asyncio.run(routes.add_assistant_faq_entry(assistant.id, _entry("Ouvert le dimanche ?", "Non."), _OWNER, db))
    deleted = asyncio.run(routes.delete_assistant_faq_entry(assistant.id, 0, _OWNER, db))
    dismissed = asyncio.run(routes.dismiss_assistant_unanswered_question(assistant.id, 0, _OWNER, db))
    listed = asyncio.run(routes.get_assistant_faq(assistant.id, _OWNER, db))

    assert (empty.faq, [item.question for item in empty.unanswered]) == (
        [],
        ["Livrez-vous à domicile ?", "Prêtez-vous un véhicule ?"],
    )
    assert [(item.question, item.answer) for item in added.faq] == [
        ("Livrez-vous à domicile ?", "Oui, dans un rayon de 20 km.")
    ]
    # The question answered left the unanswered list on its own.
    assert added.faq[0].created_at is not None
    assert [item.question for item in added.unanswered] == ["Prêtez-vous un véhicule ?"]
    assert updated.faq[0].answer == "Oui, partout en Bretagne."
    assert (deleted.status_code, dismissed.status_code) == (204, 204)
    assert [item.question for item in listed.faq] == ["Ouvert le dimanche ?"] and listed.unanswered == []
    assert _status_of(routes.get_assistant_faq(assistant.id, _STRANGER, db)) == 404
    assert _status_of(routes.add_assistant_faq_entry(assistant.id, _entry(), _STRANGER, db)) == 404
    assert _status_of(routes.update_assistant_faq_entry(assistant.id, 5, _entry(), _OWNER, db)) == 404
    assert _status_of(routes.delete_assistant_faq_entry(assistant.id, -1, _OWNER, db)) == 404
    assert _status_of(routes.dismiss_assistant_unanswered_question(assistant.id, 0, _OWNER, db)) == 404
    assert _status_of(routes.add_assistant_faq_entry(assistant.id, _entry(answer=" "), _OWNER, db)) == 400
    assert _status_of(routes.update_assistant_faq_entry(assistant.id, 0, _entry(question=""), _OWNER, db)) == 400


def test_the_client_answers_from_its_space_and_the_page_lists_both(db: Session) -> None:
    assistant = _assistant(db)
    token = AiAssistantClientLinks.token(assistant.id)
    ai_assistant_faq_service.record_unanswered(db, assistant, "Livrez-vous à domicile ?")
    ai_assistant_faq_service.record_unanswered(db, assistant, "Prêtez-vous un véhicule ?")

    added = asyncio.run(client_routes.add_client_faq_entry(token, _entry(), VISITOR_REQUEST, db))
    dismissed = asyncio.run(client_routes.dismiss_client_unanswered_question(token, 0, VISITOR_REQUEST, db))
    page = asyncio.run(client_routes.get_client_space(token, VISITOR_REQUEST, db))

    assert [item.question for item in added.faq] == ["Livrez-vous à domicile ?"]
    assert [item.question for item in added.unanswered] == ["Prêtez-vous un véhicule ?"]
    assert dismissed.status_code == 204
    assert [item.answer for item in page.faq] == ["Oui, dans un rayon de 20 km."] and page.unanswered == []
    assert _status_of(client_routes.dismiss_client_unanswered_question(token, 0, VISITOR_REQUEST, db)) == 404
    assert _status_of(client_routes.add_client_faq_entry(token, _entry(question=" "), VISITOR_REQUEST, db)) == 400
    assert (
        _status_of(client_routes.add_client_faq_entry("12.abc.AAAAAAAAAAAAAAAA", _entry(), VISITOR_REQUEST, db)) == 404
    )


def test_a_chat_files_the_unanswered_question_unless_the_visit_is_internal(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db, status="active")
    monkeypatch.setattr(
        widget_routes.ai_assistant_chat_service,
        "answer",
        AsyncCallRecorder(result=ChatAnswer(reply="Je note votre question.", unanswered_question="Livraison ?")),
    )
    replies: list[str] = []

    for session_id, internal in (("visitor", False), ("operator", True), ("other", False)):
        payload = AiAssistantChatRequest(
            messages=[AiAssistantChatMessage(role="user", content="Vous livrez ?")],
            session_id=session_id,
            internal=internal,
        )
        replies.append(
            asyncio.run(widget_routes.chat_with_assistant(assistant.slug, payload, VISITOR_REQUEST, db)).reply
        )

    db.refresh(assistant)
    [question] = ai_assistant_faq_service.unanswered_of(assistant.knowledge_json)
    assert (question.question, question.count) == ("Livraison ?", 2)
    assert replies == ["Je note votre question."] * 3
    assert db.query(AiAssistantConversation).count() == 3


def test_a_failure_to_file_the_question_never_costs_the_visitor_the_reply(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db, status="active")
    monkeypatch.setattr(
        widget_routes.ai_assistant_chat_service,
        "answer",
        AsyncCallRecorder(result=ChatAnswer(reply="Je note votre question.", unanswered_question="Livraison ?")),
    )

    def broken(db: Session, assistant: AiAssistant, question: str) -> None:
        raise RuntimeError("database gone")

    monkeypatch.setattr(widget_routes.ai_assistant_faq_service, "record_unanswered", broken)
    payload = AiAssistantChatRequest(messages=[AiAssistantChatMessage(role="user", content="Vous livrez ?")])

    answered = asyncio.run(widget_routes.chat_with_assistant(assistant.slug, payload, VISITOR_REQUEST, db))

    assert answered.reply == "Je note votre question."
    assert db.query(AiAssistantConversation).count() == 1
