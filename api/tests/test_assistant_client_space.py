"""
The client space of a sold assistant: its magic link, what the page reads and changes, and its isolation.

The email sender, Stripe and the activity log are mocked; the database is an in-memory SQLite. Routes are
called directly.
"""

import asyncio
import importlib
import pkgutil
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

import api.v1.routes.ai_assistant_client_space as routes
import api.v1.routes.ai_assistants as owner_routes
import models
import services.ai_assistant.client_space_service as client_space_module
import services.email_sending_service as email_sending_module
from core.config import settings
from core.database import Base
from enums.ai_assistant_request import AiAssistantRequestType
from enums.assistant_widget_language import AssistantWidgetLanguage
from models.ai_assistant import AiAssistant
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_request import AiAssistantRequest
from models.ai_assistant_subscription import AiAssistantSubscription
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant_client_space import AiAssistantClientLinkRequest, AiAssistantClientSettingsUpdate
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.request_alerts import AlertSms
from services.ai_assistant.request_email import AiAssistantRequestEmail, RequestEmailContent
from services.rate_limiter import SlidingWindowRateLimiter
from services.sms.gsm_segments import segment_count

for _module in pkgutil.iter_modules(models.__path__):
    importlib.import_module("models." + _module.name)

_VISITOR = Request({"type": "http", "headers": [], "client": ("203.0.113.9", 0)})
_LINK = "demo.dibodev.fr/client/1234.tneuo0.K4lzdHZLLanlAxWK"


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=7, name="Dibodev", email="operateur@dibodev.fr", hashed_password="x"))
    session.add(User(id=8, name="Autre", email="autre@exemple.fr", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


class _Recorder:
    """Collects the calls of a mocked async function."""

    def __init__(self, result: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = result

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.result


@pytest.fixture(autouse=True)
def fresh_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with empty rate-limit buckets."""
    monkeypatch.setattr(routes, "assistant_client_limiter", SlidingWindowRateLimiter(120, 300))
    monkeypatch.setattr(routes, "assistant_client_renew_limiter", SlidingWindowRateLimiter(3, 3600))
    monkeypatch.setattr(routes, "assistant_client_renew_daily_limiter", SlidingWindowRateLimiter(6, 86400))


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mock the email sender and the activity log."""
    email = _Recorder({"success": True})
    logged: list[dict[str, Any]] = []
    monkeypatch.setattr(email_sending_module.EmailSendingService, "send_via_user_identity", email)
    monkeypatch.setattr(client_space_module.activity_log_service, "record", lambda **kwargs: logged.append(kwargs))
    return {"email": email, "logged": logged}


def _assistant(
    db: Session, *, business_name: str = "Toitures Morel", status: str = "delivered", **fields: Any
) -> AiAssistant:
    prospect = ProspectDB(name=business_name, category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name=business_name, prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = status
    assistant.email = "patron@toitures-morel.fr"
    for field, value in fields.items():
        setattr(assistant, field, value)
    db.commit()
    return assistant


def _request(db: Session, assistant: AiAssistant, **fields: Any) -> AiAssistantRequest:
    values: dict[str, Any] = {
        "user_id": assistant.user_id,
        "prospect_id": assistant.prospect_id,
        "assistant_id": assistant.id,
        "name": "Marc Dubois",
        "contact": "06 98 76 54 32",
        "type": "quote",
        "need": "Des tuiles ont bougé",
        "created_at": datetime(2026, 9, 14, 8, 5),
    }
    values.update(fields)
    record = AiAssistantRequest(**values)
    db.add(record)
    db.commit()
    return record


def _token(assistant: AiAssistant, *, now: datetime | None = None) -> str:
    return AiAssistantClientLinks.token(assistant.id, now=now)


def _status_of(call: Any) -> tuple[int, str]:
    with pytest.raises(HTTPException) as caught:
        asyncio.run(call)
    return caught.value.status_code, str(caught.value.detail)


def test_the_link_is_short_signed_canonical_bound_to_its_assistant_and_expires() -> None:
    now = datetime(2026, 9, 24, 12, 0)
    token = AiAssistantClientLinks.token(42, now=now)
    _assistant_id, expiry, signature = token.split(".")
    longer = f"42.{AiAssistantClientLinks._base36(int(expiry, 36) + 86400)}.{signature}"

    assert len(token) <= 30
    assert AiAssistantClientLinks.read(token, now=now + timedelta(days=29)).is_expired is False
    assert AiAssistantClientLinks.read(token, now=now + timedelta(days=31)).is_expired is True
    for forged in (f"43.{expiry}.{signature}", longer, f"042.{expiry}.{signature}", token + "\n", "../../etc"):
        assert AiAssistantClientLinks.read(forged, now=now) is None
    assert AiAssistantClientLinks.read(token.replace("42", "٤٢", 1), now=now) is None
    assert AiAssistantClientLinks.sms_link(42, now=now) == AiAssistantClientLinks.page_url(token).split("://")[1]


def test_the_page_shows_the_assistant_requests_report_settings_and_subscription(db: Session) -> None:
    assistant = _assistant(db, alert_phone_e164="+33612345678", languages=["fr", "en", "it"])
    other = _assistant(db, business_name="Garage Martin")
    _request(db, assistant, status="handled", created_at=datetime(2026, 9, 20, 9, 0))
    _request(db, assistant, photos_json=[{"url": "https://cdn.example/p1.jpg"}], received_outside_hours=True)
    _request(db, assistant, created_at=datetime(2026, 9, 10, 9, 0))
    _request(db, assistant, is_test=True)
    _request(db, other)
    db.add(
        AiAssistantReport(
            user_id=7,
            assistant_id=assistant.id,
            month="2026-08",
            stats_json={
                "conversations": 12,
                "requests": 4,
                "handled": 2,
                "average_handling_hours": 5.0,
                "languages": [{"code": "lu", "share_pct": 25}],
            },
        )
    )
    db.add(
        AiAssistantSubscription(
            user_id=7,
            ai_assistant_id=assistant.id,
            amount_cents=7900,
            interval="month",
            status="active",
            stripe_customer_id="cus_1",
            current_period_end=datetime(2026, 10, 12, 8, 0),
            cancel_at_period_end=True,
        )
    )
    db.commit()

    page = asyncio.run(routes.get_client_space(_token(assistant), _VISITOR, db))

    assert (page.business_name, page.pending_count) == ("Toitures Morel", 2)
    # The requests still waiting come first, the handled ones after.
    assert [(item.status.value, item.received_label) for item in page.requests] == [
        ("new", "14/09 à 10:05"),
        ("new", "10/09 à 11:00"),
        ("handled", "20/09 à 11:00"),
    ]
    assert page.requests[0].photo_urls == ["https://cdn.example/p1.jpg"]
    assert page.requests[0].type is AiAssistantRequestType.QUOTE
    assert page.report is not None and page.report.month_label == "août 2026"
    assert page.report.languages_line == "luxembourgeois 25 %"
    assert page.report.handling_line == "2 demandes marquées traitées, en 5 h en moyenne."
    assert page.settings.languages == [AssistantWidgetLanguage.FR, AssistantWidgetLanguage.EN]
    assert page.settings.alert_phone == "+33612345678"
    assert page.subscription is not None
    assert (page.subscription.price_label, page.subscription.period_end_label) == ("79 €/mois", "12/10/2026")
    assert (page.subscription.cancel_scheduled, page.subscription.can_manage) == (True, True)


def test_a_token_never_reaches_another_assistant(db: Session) -> None:
    assistant = _assistant(db)
    other = _assistant(db, business_name="Garage Martin")
    foreign = _request(db, other)
    own = _request(db, assistant)
    token = _token(assistant)

    status_code, _detail = _status_of(routes.mark_client_request_handled(token, foreign.id, _VISITOR, db))
    handled = asyncio.run(routes.mark_client_request_handled(token, own.id, _VISITOR, db))

    assert status_code == 404
    assert handled.status.value == "handled"
    db.refresh(foreign)
    assert foreign.status == "new"


def test_an_expired_link_asks_for_a_new_one_and_a_forged_or_demo_link_opens_nothing(db: Session) -> None:
    sold = _assistant(db)
    demo = _assistant(db, business_name="Démo Dupont", status="active")
    deleted = _assistant(db, business_name="Garage Fermé", deleted_at=datetime(2026, 9, 1))
    expired = _token(sold, now=datetime.now(UTC) - timedelta(days=31))

    assert _status_of(routes.get_client_space(expired, _VISITOR, db)) == (
        401,
        "Ce lien a expiré : demandez un nouveau lien.",
    )
    for token in (_token(demo), _token(deleted), "12.abc.AAAAAAAAAAAAAAAA", "n'importe quoi"):
        assert _status_of(routes.get_client_space(token, _VISITOR, db))[0] == 404


def test_the_client_changes_only_its_own_settings_and_keeps_the_operator_languages(
    db: Session, outbox: dict[str, Any]
) -> None:
    assistant = _assistant(db, languages=["fr", "it"])
    token = _token(assistant)

    saved = asyncio.run(
        routes.update_client_settings(
            token,
            AiAssistantClientSettingsUpdate(
                assistant_name="Léa", languages=["fr", "lu"], alert_phone="06 12 34 56 78", alert_sms_enabled=False
            ),
            _VISITOR,
            db,
        )
    )
    untouched = asyncio.run(
        routes.update_client_settings(token, AiAssistantClientSettingsUpdate(languages=None), _VISITOR, db)
    )

    assert (saved.assistant_name, saved.alert_phone, saved.alert_sms_enabled) == ("Léa", "+33612345678", False)
    assert saved.languages == [AssistantWidgetLanguage.FR, AssistantWidgetLanguage.LU]
    assert untouched.languages == saved.languages
    db.refresh(assistant)
    # « it » was set by the operator and is not offered in the space: it stays.
    assert assistant.languages == ["fr", "lu", "it"]
    with pytest.raises(ValueError):
        AiAssistantClientSettingsUpdate(languages=["xx"])
    assert "eu_only" not in AiAssistantClientSettingsUpdate.model_fields


def test_a_bad_or_foreign_alert_mobile_saves_nothing(db: Session, outbox: dict[str, Any]) -> None:
    assistant = _assistant(db, alert_phone_e164="+33612345678")
    token = _token(assistant)

    for phone in ("01 23 45 67 89", "+44 7700 900123"):
        status_code, _detail = _status_of(
            routes.update_client_settings(
                token, AiAssistantClientSettingsUpdate(assistant_name="Zoé", alert_phone=phone), _VISITOR, db
            )
        )
        assert status_code == 422
    db.refresh(assistant)
    assert (assistant.assistant_name, assistant.alert_phone_e164) == ("Sofia", "+33612345678")
    assert outbox["email"].calls == [] and outbox["logged"] == []


def test_a_new_alert_mobile_is_announced_to_the_business_and_the_operator(db: Session, outbox: dict[str, Any]) -> None:
    assistant = _assistant(db, alert_phone_e164="+33612345678")
    token = _token(assistant)

    asyncio.run(
        routes.update_client_settings(
            token, AiAssistantClientSettingsUpdate(alert_phone="+352 621 123 456"), _VISITOR, db
        )
    )
    asyncio.run(
        routes.update_client_settings(token, AiAssistantClientSettingsUpdate(assistant_name="Léa"), _VISITOR, db)
    )

    [notice] = outbox["email"].calls
    assert (notice["recipient_email"], notice["subject"]) == (
        "patron@toitures-morel.fr",
        "Votre mobile d'alerte a été modifié",
    )
    assert "se terminant par <strong>56</strong>" in notice["body_html"] and "621" not in notice["body_html"]
    [entry] = outbox["logged"]
    assert entry["detail"] == "+33612345678 → +352621123456"


def test_the_billing_portal_returns_to_the_client_space(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    import services.assistant_subscription_service as subscription_module

    assistant = _assistant(db)
    token = _token(assistant)
    sessions: list[dict[str, str]] = []

    def create(**kwargs: str) -> SimpleNamespace:
        sessions.append(kwargs)
        return SimpleNamespace(url="https://billing.stripe.com/p/session_1")

    monkeypatch.setattr(subscription_module.settings, "stripe_secret_key", "sk_test_x", raising=False)
    monkeypatch.setattr(
        subscription_module.assistant_subscription_service._stripe.billing_portal.Session, "create", create
    )

    assert _status_of(routes.open_client_billing_portal(token, _VISITOR, db))[0] == 404
    db.add(
        AiAssistantSubscription(
            user_id=7, ai_assistant_id=assistant.id, amount_cents=7900, status="active", stripe_customer_id="cus_9"
        )
    )
    db.commit()
    portal = asyncio.run(routes.open_client_billing_portal(token, _VISITOR, db))

    assert portal.url == "https://billing.stripe.com/p/session_1"
    assert sessions == [
        {"customer": "cus_9", "return_url": f"{settings.demo_host_base_url.rstrip('/')}/client/{token}"}
    ]


def test_a_recently_expired_link_emails_a_fresh_one_within_the_limits(db: Session, outbox: dict[str, Any]) -> None:
    assistant = _assistant(db)
    expired = _token(assistant, now=datetime.now(UTC) - timedelta(days=40))
    forgotten = _token(assistant, now=datetime.now(UTC) - timedelta(days=150))

    answers = [asyncio.run(routes.renew_client_link(expired, _VISITOR, db)).sent for _ in range(3)]
    limited = _status_of(routes.renew_client_link(expired, _VISITOR, db))
    too_old = _status_of(routes.renew_client_link(forgotten, _VISITOR, db))

    assert answers == [True, True, True]
    assert (limited[0], too_old[0]) == (429, 404)
    email = outbox["email"].calls[0]
    assert (email["recipient_email"], email["is_transactional"]) == ("patron@toitures-morel.fr", True)
    fresh = email["body_html"].split("/client/")[1].split('"')[0]
    assert AiAssistantClientLinks.read(fresh).is_expired is False


def test_the_operator_issues_the_link_of_a_sold_assistant_only(db: Session, outbox: dict[str, Any]) -> None:
    sold = _assistant(db)
    demo = _assistant(db, business_name="Démo Dupont", status="active")
    silent = _assistant(db, business_name="Sans Adresse", email=None)
    operator = SimpleNamespace(id=7)

    copied = asyncio.run(
        owner_routes.issue_assistant_client_link(sold.id, AiAssistantClientLinkRequest(), operator, db)
    )
    sent = asyncio.run(
        owner_routes.issue_assistant_client_link(sold.id, AiAssistantClientLinkRequest(send=True), operator, db)
    )
    nowhere = asyncio.run(
        owner_routes.issue_assistant_client_link(silent.id, AiAssistantClientLinkRequest(send=True), operator, db)
    )
    refused = [
        _status_of(owner_routes.issue_assistant_client_link(assistant_id, AiAssistantClientLinkRequest(), user, db))[0]
        for assistant_id, user in ((demo.id, operator), (sold.id, SimpleNamespace(id=8)))
    ]

    assert "/client/" in copied.url and copied.sent_to is None
    assert sent.sent_to == "patron@toitures-morel.fr"
    assert (nowhere.sent_to, nowhere.send_error) == (None, "Aucune adresse email du commerçant.")
    [email] = outbox["email"].calls
    assert email["subject"] == f"Votre espace : les demandes reçues par {sold.assistant_name}"
    assert sent.url.split("/client/")[1] in email["body_html"]
    assert refused == [400, 404]


def test_the_link_email_gives_the_expiry_in_business_time(db: Session, outbox: dict[str, Any]) -> None:
    from services.ai_assistant.client_space_service import ai_assistant_client_space_service

    assistant = _assistant(db)
    # 22:30 UTC on 24 September is already the 25th in Paris: the link lasts until the 25th of October.
    delivery = asyncio.run(
        ai_assistant_client_space_service.issue_link(db, assistant, send=True, now=datetime(2026, 9, 24, 22, 30))
    )

    assert delivery.expires_at == datetime(2026, 10, 24, 22, 30)
    assert "valable jusqu'au 25/10/2026" in outbox["email"].calls[0]["body_html"]


def test_the_alert_sms_keeps_the_summary_before_the_link() -> None:
    def sms(name: str, contact: str, summary: str | None) -> str:
        return AlertSms.new_request(
            request_type=AiAssistantRequestType.QUOTE,
            name=name,
            contact=contact,
            summary=summary,
            has_photos=False,
            link=_LINK,
        )

    roomy = sms("Claire Petit", "06 11 22 33 44", "Fuite importante au plafond de la salle de bain après l'orage.")
    crowded = sms(
        "Jean-Christophe Dupont", "jean-christophe.dupont@gmail.com", "Fuite d'eau sous l'évier de la cuisine."
    )
    bare = sms("Paul", "0612345678", None)

    assert roomy.endswith(f" Suivi : {_LINK}") and "Fuite importante au plafond" in roomy
    assert _LINK not in crowded and crowded.endswith(": Fuite d'eau sous l'évier de la cuisine.")
    assert bare == f"Nouvelle demande de devis de Paul, 0612345678. Suivi : {_LINK}"
    assert all(segment_count(text) == 1 for text in (roomy, crowded, bare))


def test_the_summary_email_opens_the_client_space_and_warns_against_forwarding() -> None:
    rendered = AiAssistantRequestEmail.render(
        RequestEmailContent(
            business_name="Toitures Morel",
            assistant_name="Sofia",
            request_type=AiAssistantRequestType.QUOTE,
            visitor_name="Marc",
            contact="06 98 76 54 32",
            need="Tuiles",
            need_summary=None,
            received_at=datetime(2026, 9, 14, 10, 5),
            received_outside_hours=False,
            transcript=[],
            handled_url="https://api.example/handled",
            client_space_url="https://demo.example/client/1.abc.AAAAAAAAAAAAAAAA",
        )
    )

    assert 'href="https://demo.example/client/1.abc.AAAAAAAAAAAAAAAA"' in rendered.html
    assert "ne transférez pas cet email" in rendered.html


def test_the_scheduled_cancellation_is_read_from_stripe(db: Session) -> None:
    from services.assistant_subscription_service import AssistantSubscriptionService

    assistant = _assistant(db)
    row = AiAssistantSubscription(
        user_id=7, ai_assistant_id=assistant.id, amount_cents=7900, status="active", stripe_subscription_id="sub_1"
    )
    db.add(row)
    db.commit()
    service = AssistantSubscriptionService()

    service.update_from_stripe_subscription(db, {"id": "sub_1", "status": "active", "cancel_at_period_end": True})
    scheduled = row.cancel_at_period_end
    service.update_from_stripe_subscription(db, {"id": "sub_1", "status": "active", "cancel_at_period_end": False})

    assert (scheduled, row.cancel_at_period_end, row.status) == (True, False, "active")
