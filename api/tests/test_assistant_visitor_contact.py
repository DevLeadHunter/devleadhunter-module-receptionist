"""
What a visitor may leave as their contact: a phone number or an email the business can act on, nothing else; and
the assistant sold outside Stripe, marked so by its owner.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

import api.v1.routes.ai_assistants as owner_routes
from api.v1.routes import ai_assistant_widget as routes
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from schemas.ai_assistant import AiAssistantLeadRequest
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.request_email import AiAssistantRequestEmail
from services.ai_assistant.visitor_contact import VisitorContact
from tests.assistant_fakes import VISITOR_REQUEST


def _demo_assistant(db: Session, *, status: str = "active") -> AiAssistant:
    prospect = ProspectDB(name="Toitures Morel", category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Toitures Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = status
    assistant.email = "patron@toitures-morel.fr"
    assistant.demo_link_sent_at = datetime.now(UTC) - timedelta(days=3)
    assistant.expires_at = datetime.now(UTC) + timedelta(days=27)
    db.commit()
    return assistant


def _refusal(call: Any) -> tuple[int, str]:
    with pytest.raises(HTTPException) as caught:
        asyncio.run(call)
    return caught.value.status_code, str(caught.value.detail)


def test_phones_of_the_served_countries_are_read_with_any_separators() -> None:
    for phone in ("06 42 19 38 12", "0642193812", "06.42.19.38.12", "+33 6 42 19 38 12", "0033642193812"):
        assert VisitorContact.is_phone(phone), phone
    for phone in ("+41 79 123 45 67", "079 123 45 67", "+32 470 12 34 56", "0470 12 34 56", "+352 621 123 456"):
        assert VisitorContact.is_phone(phone), phone
    assert VisitorContact.is_phone("(06) 42-19-38-12")


def test_a_made_up_number_a_word_or_a_half_address_is_refused() -> None:
    # Too many digits for a national number (Léo's « 064219381200 »), too few, letters, a bare domain.
    for contact in ("064219381200", "06 42 19", "12345", "Jeue", "06 42 AB 38 12", "leo@dibodev", "@dibodev.fr", ""):
        assert not VisitorContact.is_reachable(contact), contact
    assert not VisitorContact.is_phone("+33 6 42 19")
    assert not VisitorContact.is_phone("+33 6 42 19 38 12 34 56 78 90")


def test_an_email_address_is_reachable_and_told_from_a_phone() -> None:
    assert VisitorContact.is_email("  leo@dibodev.fr ")
    assert VisitorContact.is_reachable("leo.guillaume@dibodev.fr")
    assert not VisitorContact.is_email("06 42 19 38 12")
    assert AiAssistantRequestEmail.is_email("leo@dibodev.fr") and not AiAssistantRequestEmail.is_email("0642193812")


def test_the_lead_route_refuses_an_unusable_contact_in_the_visitor_language(db: Session) -> None:
    assistant = _demo_assistant(db)
    for language, sentence in (("fr", "Indiquez un numéro"), ("en", "Please give a phone"), ("de", "Bitte geben Sie")):
        payload = AiAssistantLeadRequest(name="Léo", contact="064219381200", language=language, session_id="s-1")

        status, detail = _refusal(routes.submit_assistant_lead(assistant.slug, payload, VISITOR_REQUEST, db))

        assert status == 422 and detail.startswith(sentence), (language, detail)
    # An unknown language falls back on French.
    payload = AiAssistantLeadRequest(name="Léo", contact="Jeue", language="pt", session_id="s-2")
    assert _refusal(routes.submit_assistant_lead(assistant.slug, payload, VISITOR_REQUEST, db))[1].startswith(
        "Indiquez"
    )


def test_a_sale_outside_stripe_marks_the_assistant_sold_and_welcomes_the_business(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    welcomed: list[int] = []
    logged: list[dict[str, Any]] = []

    async def fake_welcome(_db: Session, assistant: AiAssistant) -> None:
        welcomed.append(assistant.id)

    monkeypatch.setattr(owner_routes.ai_assistant_client_space_service, "try_send_welcome", fake_welcome)
    monkeypatch.setattr(owner_routes.activity_log_service, "record", lambda **kwargs: logged.append(kwargs))
    demo = _demo_assistant(db)
    expired = _demo_assistant(db, status="expired")
    operator = SimpleNamespace(id=7, email="operateur@dibodev.fr")

    sold = asyncio.run(owner_routes.deliver_assistant(demo.id, operator, db))
    revived = asyncio.run(owner_routes.deliver_assistant(expired.id, operator, db))
    again = _refusal(owner_routes.deliver_assistant(demo.id, operator, db))
    someone_else = _refusal(owner_routes.deliver_assistant(demo.id, SimpleNamespace(id=8, email="x@y.fr"), db))

    assert (sold.status, revived.status) == ("delivered", "delivered")
    assert db.get(AiAssistant, demo.id).status == "delivered"
    assert welcomed == [demo.id, expired.id]
    assert [entry["action"] for entry in logged] == ["assistant_marked_sold", "assistant_marked_sold"]
    assert again == (400, "Cet assistant est déjà vendu.")
    assert someone_else[0] == 404
