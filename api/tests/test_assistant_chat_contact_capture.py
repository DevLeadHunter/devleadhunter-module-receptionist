"""
A phone number or an email the visitor types in the chat becomes their request, like the contact form makes it:
read with the form's rule, never a date, an hour or the business's own number, one request per widget session.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

import api.v1.routes.ai_assistant_widget as routes
import services.ai_assistant.chat_service as chat_module
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from schemas.ai_assistant import AiAssistantChatMessage, AiAssistantChatRequest, AiAssistantLeadRequest
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.chat_contact_capture import AiAssistantChatContactCapture
from services.ai_assistant.chat_service import ChatAnswer
from services.rate_limiter import SlidingWindowRateLimiter
from tests.assistant_fakes import VISITOR_REQUEST, AsyncCallRecorder

_BUSINESS_PHONE = "02 99 12 34 56"


@pytest.fixture
def scheduled(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Fresh rate limits, the model answering, and the requests' background follow-up recorded instead of run."""
    follow_ups: list[int] = []
    monkeypatch.setattr(routes, "assistant_chat_limiter", SlidingWindowRateLimiter(30, 300))
    monkeypatch.setattr(routes, "assistant_lead_limiter", SlidingWindowRateLimiter(8, 300))
    monkeypatch.setattr(routes.ai_assistant_request_follow_up, "schedule_follow_up", follow_ups.append)
    monkeypatch.setattr(
        routes.ai_assistant_chat_service, "answer", AsyncCallRecorder(result=ChatAnswer(reply="Bien noté, merci."))
    )
    return follow_ups


def _assistant(db: Session) -> AiAssistant:
    prospect = ProspectDB(name="Toitures Morel", category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db,
        user_id=7,
        business_name="Toitures Morel",
        prospect_id=prospect.id,
        phone=_BUSINESS_PHONE,
        country="FR",
        use_brand_color=False,
    )
    assistant.status = "active"
    db.commit()
    return assistant


def _chat(
    db: Session,
    assistant: AiAssistant,
    content: str,
    *,
    session_id: str | None = "s1",
    visitor_name: str | None = None,
    internal: bool = False,
) -> Any:
    payload = AiAssistantChatRequest(
        messages=[AiAssistantChatMessage(role="user", content=content)],
        session_id=session_id,
        language="fr",
        visitor_name=visitor_name,
        internal=internal,
    )
    return asyncio.run(routes.chat_with_assistant(assistant.slug, payload, VISITOR_REQUEST, db))


def test_a_phone_or_an_email_in_a_message_is_read_like_the_form_reads_it() -> None:
    read = AiAssistantChatContactCapture.contact_in

    assert read("Rappelez-moi au 06 12 34 56 78 svp") == "06 12 34 56 78"
    assert read("Mon numéro : +33 6 12 34 56 78.") == "+33 6 12 34 56 78"
    assert read("06.12.34.56.78, merci") == "06.12.34.56.78"
    assert read("Écrivez-moi à jean.dupont@gmail.com.") == "jean.dupont@gmail.com"
    assert read("0470 12 34 56") == "0470 12 34 56"
    assert read("+352 621 123 456") == "+352 621 123 456"
    # A Luxembourg mobile is written without a trunk zero.
    assert read("621 123 456") == "621 123 456"
    # The last contact given wins, as a visitor correcting themselves means it.
    assert read("marie@exemple.fr ou plutôt 06 12 34 56 78 hier soir") == "06 12 34 56 78"


def test_dates_hours_figures_and_the_business_contacts_are_never_taken() -> None:
    read = AiAssistantChatContactCapture.contact_in
    business = (_BUSINESS_PHONE, "contact@toitures-morel.fr")

    for message in (
        "Je voudrais un rendez-vous le 01/10/2026 14h",
        "le 01/10/2026 à 14h30, c'est possible ?",
        "Mon SIREN est 123 456 789",
        "Le devis fait 1 500 €, pour 250000 euros de travaux",
        "Vous êtes bien au 02 99 12 34 56 ?",
        "Vous êtes bien au +33 2 99 12 34 56 ?",
        "J'ai écrit à contact@toitures-morel.fr",
        "064219381200",
    ):
        assert read(message, business_contacts=business) is None, message


def test_the_chat_files_the_contact_as_the_session_request_and_the_form_then_updates_it(
    db: Session, scheduled: list[int]
) -> None:
    assistant = _assistant(db)

    first = _chat(
        db, assistant, "Bonjour, une fuite sur mon toit, rappelez-moi au 06 12 34 56 78", visitor_name="Julie"
    )
    lead = AiAssistantLeadRequest(
        name="Julie Roux", contact="06 12 34 56 78", need="Fuite de toiture", language="fr", session_id="s1"
    )
    asyncio.run(routes.submit_assistant_lead(assistant.slug, lead, VISITOR_REQUEST, db))

    assert first.reply == "Bien noté, merci."
    assert first.captured_contact is not None
    assert (first.captured_contact.name, first.captured_contact.contact) == ("Julie", "06 12 34 56 78")
    [request] = db.query(AiAssistantRequest).all()
    [conversation] = db.query(AiAssistantConversation).all()
    assert (request.session_id, request.conversation_id, request.is_test) == ("s1", conversation.id, False)
    # The form left afterwards completes the same request instead of adding a second one.
    assert (request.name, request.need) == ("Julie Roux", "Fuite de toiture")
    assert scheduled == [request.id, request.id]


def test_a_visitor_without_a_name_is_filed_as_a_visitor_until_they_give_one(db: Session, scheduled: list[int]) -> None:
    assistant = _assistant(db)

    nameless = _chat(db, assistant, "06 12 34 56 78")
    corrected = _chat(db, assistant, "Pardon, c'est le 06 12 34 56 79")
    named = _chat(db, assistant, "Je suis Marc, au 06 12 34 56 79", visitor_name="Marc")
    repeated = _chat(db, assistant, "Toujours le 06 12 34 56 79")
    quiet = _chat(db, assistant, "Vous travaillez le samedi ?")

    assert nameless.captured_contact is not None and nameless.captured_contact.name == "Visiteur"
    assert corrected.captured_contact is not None and corrected.captured_contact.contact == "06 12 34 56 79"
    assert named.captured_contact is not None and named.captured_contact.name == "Marc"
    # Once named, the request keeps the name when a later message only repeats the number.
    assert repeated.captured_contact is not None and repeated.captured_contact.name == "Marc"
    assert quiet.captured_contact is None
    [request] = db.query(AiAssistantRequest).all()
    assert (request.name, request.contact) == ("Marc", "06 12 34 56 79")


def test_a_test_visit_files_a_test_request_and_a_turn_without_session_files_none(
    db: Session, scheduled: list[int]
) -> None:
    assistant = _assistant(db)

    internal = _chat(db, assistant, "au 06 12 34 56 78", session_id="operator", internal=True)
    sessionless = _chat(db, assistant, "au 06 12 34 56 78", session_id=None)
    business = _chat(db, assistant, "C'est bien le 02 99 12 34 56 ?", session_id="s2")

    assert internal.captured_contact is not None
    assert sessionless.captured_contact is None and business.captured_contact is None
    [request] = db.query(AiAssistantRequest).all()
    assert (request.session_id, request.is_test) == ("operator", True)


def test_a_failure_to_file_the_contact_never_costs_the_visitor_the_reply(
    db: Session, scheduled: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)

    def broken_capture(db: Session, **fields: Any) -> Any:
        raise RuntimeError("database gone")

    monkeypatch.setattr(routes.ai_assistant_chat_contact_capture.__class__, "capture", broken_capture)

    answered = _chat(db, assistant, "Rappelez-moi au 06 12 34 56 78")

    assert (answered.reply, answered.captured_contact) == ("Bien noté, merci.", None)
    assert db.query(AiAssistantRequest).count() == 0


def test_the_stream_closes_on_the_captured_contact(
    db: Session, scheduled: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    monkeypatch.setattr(routes, "SessionLocal", sessionmaker(bind=db.get_bind()))

    async def chat_stream(usage: Any, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        yield "Merci, je transmets."

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat_stream", chat_stream)
    payload = AiAssistantChatRequest(
        messages=[AiAssistantChatMessage(role="user", content="Rappelez-moi au 06 12 34 56 78")],
        session_id="s1",
        visitor_name="Julie",
    )

    async def frames() -> list[str]:
        response = await routes.stream_chat_with_assistant(assistant.slug, payload, VISITOR_REQUEST, db)
        return [chunk if isinstance(chunk, str) else chunk.decode() async for chunk in response.body_iterator]

    closing = json.loads(asyncio.run(frames())[-1][len("data: ") :])

    assert closing["done"] is True and closing["daily_limit_reached"] is False
    assert closing["captured_contact"] == {"name": "Julie", "contact": "06 12 34 56 78"}
    assert db.query(AiAssistantRequest).count() == 1
