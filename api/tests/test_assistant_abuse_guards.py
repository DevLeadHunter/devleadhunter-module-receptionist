"""The receptionist's guards against abuse of its public surface: forged addresses, floods, test bookings, muted
businesses, and alert numbers that are not served mobiles."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette.requests import Request

import services.rate_limiter as limiter_module
from api.v1.routes import ai_assistant_widget as routes
from api.v1.routes.ai_assistant_common import client_ip
from enums.ai_assistant_request import AiAssistantRequestType
from models.ai_assistant import AiAssistant
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from schemas.ai_assistant import AiAssistantBookingChoice, AiAssistantLeadRequest
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.business_mailer import AiAssistantBusinessMailer
from services.ai_assistant.request_alerts import ai_assistant_request_alerts
from services.ai_assistant.request_service import AiAssistantRequestService
from services.rate_limiter import SlidingWindowRateLimiter
from services.sms.phone_normalizer import to_served_mobile
from tests.assistant_fakes import VISITOR_REQUEST


def _request_with(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()],
        "client": ("10.0.0.5", 1234),
    }
    return Request(scope)


def _delivered_assistant(db: Session, *, do_not_contact: bool = False) -> AiAssistant:
    prospect = ProspectDB(
        name="Toitures Morel",
        category="Couvreur",
        source="google",
        confidence=2,
        user_id=7,
        email="patron@toitures-morel.fr",
        do_not_contact=do_not_contact,
    )
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Toitures Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = "delivered"
    assistant.alert_phone_e164 = "+33612345678"
    db.commit()
    return assistant


def test_the_visitor_address_is_the_one_the_proxy_appended() -> None:
    # nginx appends the address it saw: the first entry is whatever the visitor typed in the header.
    assert client_ip(_request_with({"X-Forwarded-For": "1.2.3.4, 203.0.113.9"})) == "203.0.113.9"
    assert client_ip(_request_with({"X-Forwarded-For": "203.0.113.9"})) == "203.0.113.9"
    assert client_ip(_request_with({})) == "10.0.0.5"


def test_a_flood_of_new_keys_frees_only_the_oldest_budgets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limiter_module, "_MAX_TRACKED_KEYS", 4)
    limiter = SlidingWindowRateLimiter(max_events=1, window_seconds=60)
    for key in ("k1", "k2", "k3", "k4"):
        assert limiter.allow(key)

    assert limiter.allow("k5")
    # k1 and k2 were forgotten; k3 and k4 still hold their spent budget.
    assert limiter.allow("k1") and not limiter.allow("k3") and not limiter.allow("k4")


def test_a_test_visit_never_books_in_the_agenda(db: Session) -> None:
    assistant = _delivered_assistant(db)
    payload = AiAssistantLeadRequest(
        name="Julie Roux",
        contact="06 11 22 33 44",
        session_id="session-1",
        internal=True,
        booking=AiAssistantBookingChoice(start=datetime(2026, 10, 1, 14, 0, tzinfo=UTC), type=None),
    )

    with pytest.raises(HTTPException) as refused:
        asyncio.run(routes.submit_assistant_lead(assistant.slug, payload, VISITOR_REQUEST, db))

    assert refused.value.status_code == 422
    assert refused.value.detail == routes._TEST_BOOKING_REFUSED
    assert db.query(AiAssistantRequest).count() == 0


def test_a_start_outside_the_bookable_years_is_refused_by_the_schema() -> None:
    with pytest.raises(ValueError):
        AiAssistantBookingChoice(start=datetime(9999, 12, 31, 23, 0, tzinfo=UTC), type=None)


def test_a_business_flagged_do_not_contact_gets_neither_email_nor_alert(db: Session) -> None:
    assistant = _delivered_assistant(db, do_not_contact=True)
    request = AiAssistantRequest(
        user_id=7,
        prospect_id=assistant.prospect_id,
        assistant_id=assistant.id,
        name="Marc Dubois",
        contact="06 98 76 54 32",
        need="Un devis",
        type=AiAssistantRequestType.QUOTE.value,
    )
    db.add(request)
    db.commit()

    assert AiAssistantBusinessMailer.is_muted(db, assistant)
    assert AiAssistantBusinessMailer.business_email(db, assistant) is None
    asyncio.run(ai_assistant_request_alerts.alert_owner(db, request, assistant, []))
    db.refresh(request)
    assert request.owner_alerted_at is None and request.sms_due_at is None


def test_a_request_made_urgent_by_a_late_photo_gets_its_sms_planned(db: Session) -> None:
    assistant = _delivered_assistant(db)
    request = AiAssistantRequest(
        user_id=7,
        prospect_id=assistant.prospect_id,
        assistant_id=assistant.id,
        name="Marc Dubois",
        contact="06 98 76 54 32",
        need="Une question",
        type=AiAssistantRequestType.URGENT.value,
        owner_alerted_at=datetime(2026, 9, 24, 12, 0),
    )
    db.add(request)
    db.commit()

    AiAssistantRequestService._plan_sms_for_late_urgency(db, request)
    assert request.sms_due_at is not None

    already_texted = AiAssistantRequest(
        user_id=7,
        prospect_id=assistant.prospect_id,
        assistant_id=assistant.id,
        name="Marc Dubois",
        contact="06 98 76 54 32",
        type=AiAssistantRequestType.URGENT.value,
        owner_alerted_at=datetime(2026, 9, 24, 12, 0),
        sms_sent_at=datetime(2026, 9, 24, 12, 1),
    )
    AiAssistantRequestService._plan_sms_for_late_urgency(db, already_texted)
    assert already_texted.sms_due_at is None


def test_served_mobiles_are_told_from_landlines_and_other_countries() -> None:
    assert to_served_mobile("06 12 34 56 78") == "+33612345678"
    assert to_served_mobile("+32 470 12 34 56") == "+32470123456"
    assert to_served_mobile("+352 621 123 456") == "+352621123456"
    assert to_served_mobile("+41 79 123 45 67") == "+41791234567"
    assert to_served_mobile("+49 151 2345678") == "+491512345678"
    # Landlines of the served countries, and a mobile of another country.
    assert to_served_mobile("01 23 45 67 89") is None
    assert to_served_mobile("+32 2 511 11 11") is None
    assert to_served_mobile("+41 22 123 45 67") is None
    assert to_served_mobile("+44 7700 900123") is None
