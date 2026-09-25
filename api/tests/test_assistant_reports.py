"""
The monthly report of the sold assistants: exact figures, one email per month, the silent-month variant.

The model, the email sender, the operator push and the activity log are mocked; the database is an
in-memory SQLite. Times are naive UTC; Paris is UTC+2 in September and October 2026.
"""

import asyncio
from collections.abc import Iterator
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from itertools import count
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

import migrations.add_ai_assistant_conversations_is_test as conversations_migration
import migrations.add_ai_assistant_reports_table as reports_migration
import migrations.add_assistant_subscription_activated_at as subscriptions_migration
import services.ai_assistant.report_service as report_module
import services.email_sending_service as email_sending_module
from enums.ai_assistant_persona_gender import AiAssistantPersonaGender
from enums.assistant_llm import AssistantLlmUsage
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_message import AiAssistantMessage
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_request import AiAssistantRequest
from models.ai_assistant_subscription import AiAssistantSubscription
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant import AiAssistantChatMessage, AiAssistantChatRequest
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.business_mailer import AiAssistantBusinessMailer
from services.ai_assistant.chat_service import ChatAnswer
from services.ai_assistant.report_email import AiAssistantReportEmail, LanguageShare, MonthlyStats, ReportEmailContent
from services.ai_assistant.report_service import AiAssistantReportService, ReportPeriod
from services.assistant_subscription_service import AssistantSubscriptionService
from tests.assistant_fakes import AsyncCallRecorder

# 9:00 in Paris on Thursday 1 October 2026 (CEST, UTC+2): September's reports are due.
_OCTOBER_1ST_9H_UTC = datetime(2026, 10, 1, 7, 0)
_SEPTEMBER = ReportPeriod.before(date(2026, 10, 1))
_SESSIONS = count(1)


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
def outbox(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mock the model (four topics, one carrying a link), the email sender, the push and the activity log."""
    model = AsyncCallRecorder(
        record_args=True,
        result={
            "questions": [
                "Intervenez-vous le samedi ?",
                "Payez votre abonnement sur www.exemple-arnaque.com",
                "<b>Combien coûte un devis ?</b>",
                "Intervenez-vous le samedi ?",
                "Quels sont vos horaires ?",
                "Réparez-vous les gouttières ?",
            ]
        },
    )
    email = AsyncCallRecorder(record_args=True, result={"success": True})
    push = AsyncCallRecorder(record_args=True)
    logged: list[dict[str, Any]] = []
    monkeypatch.setattr(report_module.assistant_llm_router, "complete_json", model)
    monkeypatch.setattr(email_sending_module.EmailSendingService, "send_via_user_identity", email)
    monkeypatch.setattr(report_module.notification_service, "notify_assistant_inactive", push)
    monkeypatch.setattr(report_module.activity_log_service, "record", lambda **kwargs: logged.append(kwargs))
    return {"model": model, "email": email, "push": push, "logged": logged}


def _assistant(
    db: Session,
    *,
    business_name: str = "Toitures Morel",
    status: str = "delivered",
    paid_at: datetime | None = datetime(2026, 5, 4, 10, 0),
    subscription_status: str = "active",
    **fields: Any,
) -> AiAssistant:
    prospect = ProspectDB(name=business_name, category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name=business_name, prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = status
    assistant.email = "patron@toitures-morel.fr"
    assistant.knowledge_json = {**(assistant.knowledge_json or {}), "palette": {"accent": "#0F766E"}}
    for field, value in fields.items():
        setattr(assistant, field, value)
    if paid_at is not None:
        db.add(
            AiAssistantSubscription(
                user_id=7,
                prospect_id=prospect.id,
                ai_assistant_id=assistant.id,
                amount_cents=7900,
                status=subscription_status,
                created_at=paid_at - timedelta(days=1),
                activated_at=paid_at,
            )
        )
    db.commit()
    return assistant


def _conversation(
    db: Session,
    assistant: AiAssistant,
    *,
    started_at: datetime,
    language: str | None = "fr",
    first_message: str = "Vous intervenez le samedi ?",
    is_test: bool | None = None,
) -> AiAssistantConversation:
    conversation = AiAssistantConversation(
        user_id=assistant.user_id,
        prospect_id=assistant.prospect_id,
        assistant_id=assistant.id,
        session_id=f"session-{next(_SESSIONS)}",
        language=language,
        message_count=4,
        is_test=is_test,
        started_at=started_at,
        last_message_at=started_at,
    )
    for role, content in (
        ("user", first_message),
        ("assistant", "Oui, le samedi matin."),
        ("user", "Merci, je vous laisse mon numéro."),
        ("assistant", "Parfait, c'est noté."),
    ):
        conversation.messages.append(AiAssistantMessage(role=role, content=content, created_at=started_at))
    db.add(conversation)
    db.commit()
    return conversation


def _return(db: Session, conversation: AiAssistantConversation, *, at: datetime, message: str) -> None:
    """The same visitor writes again later, in their session's conversation."""
    conversation.messages.append(AiAssistantMessage(role="user", content=message, created_at=at))
    conversation.messages.append(AiAssistantMessage(role="assistant", content="Bien sûr.", created_at=at))
    conversation.last_message_at = at
    db.commit()


def _request(
    db: Session, assistant: AiAssistant, *, created_at: datetime, request_type: str = "question", **fields: Any
) -> AiAssistantRequest:
    request = AiAssistantRequest(
        user_id=assistant.user_id,
        prospect_id=assistant.prospect_id,
        assistant_id=assistant.id,
        name="Marc Dubois",
        contact="06 98 76 54 32",
        type=request_type,
        created_at=created_at,
        **fields,
    )
    db.add(request)
    db.commit()
    return request


def _send(db: Session, now: datetime = _OCTOBER_1ST_9H_UTC) -> int:
    return asyncio.run(AiAssistantReportService().send_due_reports(db, now=now))


def _stats(**figures: Any) -> MonthlyStats:
    defaults: dict[str, Any] = {
        "conversations": 12,
        "requests": 3,
        "quotes": 1,
        "appointments": 1,
        "urgent": 0,
        "photo_requests": 0,
        "handled": 1,
        "outside_hours_pct": None,
        "languages": (),
        "average_handling_hours": 30.0,
        "top_questions": (),
    }
    return MonthlyStats(**{**defaults, **figures})


def test_the_month_is_read_in_paris_time() -> None:
    assert _SEPTEMBER.key == "2026-09"
    assert (_SEPTEMBER.start, _SEPTEMBER.end) == (datetime(2026, 8, 31, 22, 0), datetime(2026, 9, 30, 22, 0))
    january = ReportPeriod.before(date(2027, 2, 3))
    assert (january.key, january.start, january.end) == (
        "2027-01",
        datetime(2026, 12, 31, 23, 0),
        datetime(2027, 1, 31, 23, 0),
    )
    assert ReportPeriod.of_key("2026-12") == ReportPeriod.of_month(date(2026, 12, 25))


def test_the_figures_cover_the_month_exactly_without_tests_or_other_assistants(
    db: Session, outbox: dict[str, Any]
) -> None:
    assistant = _assistant(db, eu_only=True)
    other = _assistant(db, business_name="Garage Martin")
    _conversation(db, assistant, started_at=datetime(2026, 9, 10, 9, 0))
    _conversation(db, assistant, started_at=datetime(2026, 9, 11, 9, 0), first_message="Combien pour une fuite ?")
    _conversation(db, assistant, started_at=datetime(2026, 9, 12, 9, 0), language="en", first_message="Saturdays?")
    # 23:30 in Paris on 30 September: still September.
    _conversation(db, assistant, started_at=datetime(2026, 9, 30, 21, 30), language="de-DE", first_message="Preis?")
    # A visitor from August writes again in September: their conversation counts, with its September message.
    august = _conversation(db, assistant, started_at=datetime(2026, 8, 20, 9, 0), language="lu", first_message="Août")
    _return(db, august, at=datetime(2026, 9, 18, 9, 0), message="Toujours dispo en septembre ?")
    # 23:30 in Paris on 31 August, 0:30 on 1 October, the operator testing, another assistant: left out.
    _conversation(db, assistant, started_at=datetime(2026, 8, 31, 21, 30), first_message="Fin août")
    _conversation(db, assistant, started_at=datetime(2026, 9, 30, 22, 30), first_message="Octobre")
    _conversation(db, assistant, started_at=datetime(2026, 9, 16, 9, 0), first_message="Test", is_test=True)
    _conversation(db, other, started_at=datetime(2026, 9, 15, 9, 0), first_message="Autre assistant")
    received = datetime(2026, 9, 14, 8, 0)
    _request(
        db,
        assistant,
        created_at=received,
        request_type="quote",
        channel="photo",
        received_outside_hours=True,
        status="handled",
        handled_at=received + timedelta(hours=3),
    )
    _request(db, assistant, created_at=received, request_type="quote", received_outside_hours=False)
    _request(
        db,
        assistant,
        created_at=received,
        request_type="appointment",
        received_outside_hours=True,
        status="handled",
        handled_at=received + timedelta(hours=5),
    )
    _request(db, assistant, created_at=received, request_type="urgent")
    _request(db, assistant, created_at=received, is_test=True)
    _request(db, assistant, created_at=datetime(2026, 8, 31, 21, 30), request_type="quote")
    _request(db, other, created_at=received, request_type="quote")

    stats = asyncio.run(AiAssistantReportService().compute(db, assistant, start=_SEPTEMBER.start, end=_SEPTEMBER.end))

    assert stats == MonthlyStats(
        conversations=5,
        requests=4,
        quotes=2,
        appointments=1,
        urgent=1,
        photo_requests=1,
        handled=2,
        outside_hours_pct=67,
        languages=(
            LanguageShare("fr", 40),
            LanguageShare("de", 20),
            LanguageShare("en", 20),
            LanguageShare("lu", 20),
        ),
        average_handling_hours=4.0,
        # The question carrying a link is dropped, the duplicate too, three at most.
        top_questions=("Intervenez-vous le samedi ?", "<b>Combien coûte un devis ?</b>", "Quels sont vos horaires ?"),
    )
    [call] = outbox["model"].calls
    assert call["args"][0] is AssistantLlmUsage.REPORT
    assert call["eu_only"] is True
    # Each conversation's first visitor message of the month, never the replies, the tests or other months.
    assert call["args"][1][1]["content"].splitlines() == [
        "- Toujours dispo en septembre ?",
        "- Preis?",
        "- Saturdays?",
        "- Combien pour une fuite ?",
        "- Vous intervenez le samedi ?",
    ]


def test_the_report_goes_to_the_business_with_the_operator_in_blind_copy_once(
    db: Session, outbox: dict[str, Any]
) -> None:
    assistant = _assistant(db)
    _conversation(db, assistant, started_at=datetime(2026, 9, 14, 7, 0))
    _request(
        db, assistant, created_at=datetime(2026, 9, 14, 8, 0), request_type="appointment", received_outside_hours=True
    )
    _request(db, assistant, created_at=datetime(2026, 9, 15, 8, 0), request_type="quote", received_outside_hours=False)

    first = _send(db)
    second = _send(db, _OCTOBER_1ST_9H_UTC + timedelta(hours=2))

    assert (first, second) == (1, 0)
    [email] = outbox["email"].calls
    assert (email["recipient_email"], email["bcc"], email["is_transactional"]) == (
        "patron@toitures-morel.fr",
        ["operateur@dibodev.fr"],
        True,
    )
    assert email["subject"] == (
        f"{assistant.assistant_name} en septembre : 2 demandes, 1 rendez-vous, 1 devis, 50 % en dehors de vos horaires"
    )
    assert "background:#0F766E;color:#ffffff" in email["body_html"]
    report = db.query(AiAssistantReport).one()
    assert (report.month, report.is_empty, report.attempts, report.sent_at) == (
        "2026-09",
        False,
        1,
        _OCTOBER_1ST_9H_UTC,
    )
    assert (report.stats_json["conversations"], report.stats_json["requests"]) == (1, 2)
    # One conversation is too few to tell the most asked questions: the model is not called.
    assert outbox["model"].calls == []
    assert outbox["push"].calls == []


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 10, 1, 5, 59),  # 7:59 in Paris
        datetime(2026, 10, 4, 7, 0),  # the 4th
        datetime(2026, 9, 30, 20, 0),  # still September in Paris
    ],
)
def test_reports_leave_on_the_first_three_days_of_the_month_from_8_am(
    db: Session, outbox: dict[str, Any], now: datetime
) -> None:
    _assistant(db)

    assert _send(db, now) == 0
    assert db.query(AiAssistantReport).count() == 0


def test_a_server_down_on_the_first_catches_up_until_the_third(db: Session, outbox: dict[str, Any]) -> None:
    _assistant(db)

    assert _send(db, datetime(2026, 10, 3, 6, 0)) == 1


def test_a_silent_month_sends_the_visibility_checks_and_warns_the_operator(db: Session, outbox: dict[str, Any]) -> None:
    assistant = _assistant(db)
    # No embed domain recorded: the prospect's own site, where the widget is installed, is linked.
    db.get(ProspectDB, assistant.prospect_id).website = "https://www.toitures-morel.fr/accueil"
    db.commit()
    _conversation(db, assistant, started_at=datetime(2026, 8, 20, 9, 0))
    _conversation(db, assistant, started_at=datetime(2026, 9, 20, 9, 0), is_test=True)

    assert _send(db) == 1

    [email] = outbox["email"].calls
    assert email["subject"] == f"{assistant.assistant_name} n'a reçu aucune visite en septembre"
    assert '<a href="https://toitures-morel.fr"' in email["body_html"]
    assert "fiche d'établissement Google" in email["body_html"]
    # The client's customers are sent to the client's site, never to the sales demo page.
    assert "/ia/" not in email["body_html"]
    [push] = outbox["push"].calls
    assert (push["user_id"], push["prospect_id"], push["month_label"]) == (7, assistant.prospect_id, "septembre 2026")
    assert db.query(AiAssistantReport).one().is_empty is True


def test_demos_cancelled_clients_and_last_week_payments_get_no_report(db: Session, outbox: dict[str, Any]) -> None:
    _assistant(db, business_name="Démo Dupont", status="active")
    _assistant(db, business_name="Garage Fermé", deleted_at=datetime(2026, 9, 20, 9, 0))
    _assistant(db, business_name="Plomberie Partie", subscription_status="canceled")
    _assistant(db, business_name="Sans Abonnement", paid_at=None)
    # Paid on 26 September: four days of service, the first report will be October's. An August checkout
    # left unpaid (ended canceled) does not pull the start back.
    late = _assistant(db, business_name="Plomberie Neuve", paid_at=datetime(2026, 9, 26, 10, 0))
    db.add(
        AiAssistantSubscription(
            user_id=7, ai_assistant_id=late.id, amount_cents=7900, status="canceled", created_at=datetime(2026, 8, 20)
        )
    )
    db.commit()

    assert _send(db) == 0
    assert outbox["email"].calls == []
    assert db.query(AiAssistantReport).count() == 0


def test_a_client_who_paid_mid_month_is_reported_from_the_payment(db: Session, outbox: dict[str, Any]) -> None:
    # The checkout was opened on 2 September, the payment came on the 12th.
    assistant = _assistant(db, paid_at=datetime(2026, 9, 12, 8, 0))
    db.query(AiAssistantSubscription).update({AiAssistantSubscription.created_at: datetime(2026, 9, 2)})
    db.commit()
    _conversation(db, assistant, started_at=datetime(2026, 9, 5, 9, 0))
    _request(db, assistant, created_at=datetime(2026, 9, 6, 9, 0), request_type="quote")
    _conversation(db, assistant, started_at=datetime(2026, 9, 20, 9, 0))

    assert _send(db) == 1

    report = db.query(AiAssistantReport).one()
    assert (report.stats_json["conversations"], report.stats_json["requests"]) == (1, 0)
    [email] = outbox["email"].calls
    assert email["subject"] == f"{assistant.assistant_name} en septembre : 1 conversation"
    assert "depuis sa mise en service le 12 septembre" in email["body_html"]


@pytest.mark.parametrize("status_before", ["incomplete", "active"])
def test_the_activation_is_stamped_once_when_the_client_pays(db: Session, status_before: str) -> None:
    """Stamped on the checkout completion, even when a subscription update already flipped the row to active."""
    assistant = _assistant(db, status="active", paid_at=None)
    row = AiAssistantSubscription(
        user_id=7,
        ai_assistant_id=assistant.id,
        amount_cents=7900,
        status=status_before,
        created_at=datetime(2026, 9, 2),
    )
    db.add(row)
    db.commit()
    session = {"metadata": {"assistant_subscription_id": str(row.id)}, "customer_details": {"email": "c@x.fr"}}
    service = AssistantSubscriptionService()

    service.activate_from_session(db, session)
    first = row.activated_at
    service.activate_from_session(db, session)

    assert first is not None and row.activated_at == first
    assert first > datetime(2026, 9, 2)
    assert assistant.status == "delivered"


def test_a_failed_send_is_logged_and_retried_twice_an_hour_apart(db: Session, outbox: dict[str, Any]) -> None:
    _assistant(db)
    outbox["email"].result = {"success": False, "error": "Quota Resend atteint"}

    first = _send(db)
    too_soon = _send(db, _OCTOBER_1ST_9H_UTC + timedelta(minutes=30))
    second = _send(db, _OCTOBER_1ST_9H_UTC + timedelta(hours=1))
    outbox["email"].result = {"success": True}
    third = _send(db, _OCTOBER_1ST_9H_UTC + timedelta(hours=2))
    after_success = _send(db, _OCTOBER_1ST_9H_UTC + timedelta(hours=4))

    assert (first, too_soon, second, third, after_success) == (0, 0, 0, 1, 0)
    assert len(outbox["email"].calls) == 3
    report = db.query(AiAssistantReport).one()
    assert (report.attempts, report.sent_at) == (3, _OCTOBER_1ST_9H_UTC + timedelta(hours=2))
    assert [entry["detail"] for entry in outbox["logged"]] == [
        "Quota Resend atteint (essai 1/3, nouvel essai prévu)",
        "Quota Resend atteint (essai 2/3, nouvel essai prévu)",
    ]


def test_a_failure_late_on_the_last_report_day_is_final(db: Session, outbox: dict[str, Any]) -> None:
    _assistant(db)
    outbox["email"].result = {"success": False, "error": "Quota Resend atteint"}
    # 23:30 in Paris on 3 October, then 0:30 on the 4th: the report days are over.
    late_evening = datetime(2026, 10, 3, 21, 30)

    assert _send(db, late_evening) == 0
    assert _send(db, late_evening + timedelta(hours=1)) == 0
    assert len(outbox["email"].calls) == 1
    assert [entry["detail"] for entry in outbox["logged"]] == ["Quota Resend atteint (essai 1/3, abandonné)"]


def test_a_retry_never_reaches_a_client_who_cancelled_meanwhile(db: Session, outbox: dict[str, Any]) -> None:
    _assistant(db)
    outbox["email"].result = {"success": False, "error": "Quota Resend atteint"}
    _send(db)
    db.query(AiAssistantSubscription).update({AiAssistantSubscription.status: "canceled"})
    db.commit()
    outbox["email"].result = {"success": True}

    assert _send(db, _OCTOBER_1ST_9H_UTC + timedelta(hours=2)) == 0
    assert len(outbox["email"].calls) == 1


def test_a_report_is_given_up_after_three_attempts(db: Session, outbox: dict[str, Any]) -> None:
    _assistant(db)
    outbox["email"].result = {"success": False, "error": "Boîte refusée"}

    sent = [_send(db, _OCTOBER_1ST_9H_UTC + timedelta(hours=hours)) for hours in range(5)]

    assert sent == [0, 0, 0, 0, 0]
    assert len(outbox["email"].calls) == 3
    assert outbox["logged"][-1]["detail"] == "Boîte refusée (essai 3/3, abandonné)"


def test_a_report_is_claimed_once(db: Session, outbox: dict[str, Any]) -> None:
    assistant = _assistant(db)
    service = AiAssistantReportService()

    first = asyncio.run(service.report(db, assistant, _SEPTEMBER, now=_OCTOBER_1ST_9H_UTC))
    claimed_elsewhere = asyncio.run(service.report(db, assistant, _SEPTEMBER, now=_OCTOBER_1ST_9H_UTC))

    assert (first, claimed_elsewhere) == (True, False)
    assert len(outbox["email"].calls) == 1


def test_the_business_address_falls_back_on_the_paying_client_of_a_running_subscription(db: Session) -> None:

    running = _assistant(db, business_name="Client Actif", email=None)
    cancelled = _assistant(db, business_name="Client Parti", email=None, subscription_status="canceled")
    db.query(AiAssistantSubscription).update({AiAssistantSubscription.client_email: " gerant@client.fr "})
    db.commit()

    assert AiAssistantBusinessMailer.business_email(db, running) == "gerant@client.fr"
    assert AiAssistantBusinessMailer.business_email(db, cancelled) is None


def test_without_a_business_address_the_paying_client_then_the_operator_get_it(
    db: Session, outbox: dict[str, Any]
) -> None:
    client = _assistant(db, business_name="Client Stripe", email=None)
    db.query(AiAssistantSubscription).filter(AiAssistantSubscription.ai_assistant_id == client.id).update(
        {AiAssistantSubscription.client_email: "gerant@client-stripe.fr"}
    )
    db.commit()
    _assistant(db, business_name="Sans Adresse", email=None)

    assert _send(db) == 2

    recipients = [(email["recipient_email"], email["bcc"]) for email in outbox["email"].calls]
    assert recipients == [("gerant@client-stripe.fr", ["operateur@dibodev.fr"]), ("operateur@dibodev.fr", None)]


def test_the_email_wears_a_valid_accent_escapes_texts_and_agrees_with_the_persona() -> None:
    content = ReportEmailContent(
        business_name="Garage <Martin>",
        assistant_name="Lucas",
        persona_gender=AiAssistantPersonaGender.MASCULINE,
        month_first_day=date(2026, 9, 1),
        stats=_stats(
            languages=(
                LanguageShare("fr", 70),
                LanguageShare("lu", 20),
                LanguageShare("de", 5),
                LanguageShare("xx", 5),
            ),
            top_questions=("<script>alert(1)</script>",),
        ),
        accent_color="#FFD500",
    )

    rendered = AiAssistantReportEmail.render(content)
    hostile = AiAssistantReportEmail.render(replace(content, accent_color="red;background:url(https://x.io)"))

    assert rendered.subject == "Lucas en septembre : 3 demandes, 1 rendez-vous, 1 devis"
    assert "background:#FFD500;color:#111111" in rendered.html
    assert "votre réceptionniste virtuel," in rendered.html
    assert "Garage &lt;Martin&gt;" in rendered.html
    assert "<script>" not in rendered.html and "&lt;script&gt;" in rendered.html
    assert "français 70\u00a0%, luxembourgeois 20\u00a0%, allemand 5\u00a0%, autres 5\u00a0%" in rendered.html
    assert "1 demande marquée traitée, en 30\u00a0h en moyenne." in rendered.html
    assert "url(" not in hostile.html and "background:#111111;color:#ffffff" in hostile.html


def test_the_stored_figures_read_back_identically() -> None:
    stats = _stats(languages=(LanguageShare("fr", 100),), top_questions=("Horaires ?",), outside_hours_pct=31)

    assert MonthlyStats.from_json(asdict(stats)) == stats


def test_the_client_site_is_linked_only_when_it_reads_as_a_domain() -> None:
    host = AiAssistantReportEmail.website_host

    assert host("https://www.Agence-Luma.lu/contact") == "agence-luma.lu"
    assert host("toitures-morel.fr") == "toitures-morel.fr"
    assert host('evil.fr" onclick="x') is None
    assert host("pas un site") is None
    assert host(None) is None


def test_the_dashboard_flags_a_subscriber_silent_for_30_days_only() -> None:
    now = datetime(2026, 10, 1, 12, 0)
    paid = now - timedelta(days=45)
    risk = AiAssistantReportService.is_churn_risk

    assert risk(status="delivered", subscribed_at=paid, conversations_30d=0, requests_30d=0, now=now)
    assert not risk(status="delivered", subscribed_at=paid, conversations_30d=1, requests_30d=0, now=now)
    assert not risk(status="delivered", subscribed_at=paid, conversations_30d=0, requests_30d=2, now=now)
    assert not risk(
        status="delivered", subscribed_at=now - timedelta(days=10), conversations_30d=0, requests_30d=0, now=now
    )
    assert not risk(status="delivered", subscribed_at=None, conversations_30d=0, requests_30d=0, now=now)
    assert not risk(status="active", subscribed_at=paid, conversations_30d=0, requests_30d=0, now=now)


def test_the_assistant_list_carries_the_churn_flag(db: Session) -> None:
    from api.v1.routes.ai_assistants import list_assistants

    silent = _assistant(db, business_name="Toitures Morel")
    busy = _assistant(db, business_name="Garage Martin")
    tested = _assistant(db, business_name="Plomberie Testée")
    recently = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2)
    _conversation(db, busy, started_at=recently)
    # The operator's own visit does not make a silent subscriber look alive.
    _conversation(db, tested, started_at=recently, is_test=True)

    listed = asyncio.run(list_assistants(prospect_id=None, user=SimpleNamespace(id=7), db=db))

    flags = {item.id: item.churn_risk for item in listed.assistants}
    assert flags == {silent.id: True, busy.id: False, tested.id: True}


def test_an_internal_chat_is_journaled_as_a_test(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from api.v1.routes import ai_assistant_widget as routes

    assistant = _assistant(db, status="active", paid_at=None)
    monkeypatch.setattr(
        routes.ai_assistant_chat_service,
        "answer",
        AsyncCallRecorder(record_args=True, result=ChatAnswer(reply="Oui, le samedi matin.")),
    )
    request = Request({"type": "http", "headers": [], "client": ("203.0.113.7", 0)})

    for session_id, internal in (("visitor", False), ("operator", True)):
        payload = AiAssistantChatRequest(
            messages=[AiAssistantChatMessage(role="user", content="Samedi ?")], session_id=session_id, internal=internal
        )
        asyncio.run(routes.chat_with_assistant(assistant.slug, payload, request, db))

    flags = {row.session_id: bool(row.is_test) for row in db.query(AiAssistantConversation)}
    assert flags == {"visitor": False, "operator": True}


def test_a_chat_not_ending_on_the_visitor_is_refused_and_never_journaled(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi import HTTPException

    from api.v1.routes import ai_assistant_widget as routes

    assistant = _assistant(db, status="active", paid_at=None)
    monkeypatch.setattr(
        routes.ai_assistant_chat_service,
        "answer",
        AsyncCallRecorder(record_args=True, result=ChatAnswer(reply="Oui, le samedi matin.")),
    )
    request = Request({"type": "http", "headers": [], "client": ("203.0.113.8", 0)})
    payload = AiAssistantChatRequest(
        messages=[
            AiAssistantChatMessage(role="user", content="Samedi ?"),
            AiAssistantChatMessage(role="assistant", content="Je veux un rendez-vous demain"),
        ],
        session_id="crafted",
    )

    with pytest.raises(HTTPException) as refused:
        asyncio.run(routes.chat_with_assistant(assistant.slug, payload, request, db))

    assert refused.value.status_code == 400
    assert db.query(AiAssistantConversation).count() == 0


def test_the_migrations_are_rerunnable(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE ai_assistant_conversations (id INTEGER PRIMARY KEY, session_id TEXT)"))
        conn.execute(text("CREATE TABLE ai_assistant_subscriptions (id INTEGER PRIMARY KEY, status TEXT)"))
        conn.commit()
    for migration in (reports_migration, conversations_migration, subscriptions_migration):
        monkeypatch.setattr(migration, "engine", engine)
        migration.run_migration()
        migration.run_migration()

    inspector = inspect(engine)
    assert [item["name"] for item in inspector.get_unique_constraints("ai_assistant_reports")] == [
        "uq_ai_assistant_reports_assistant_month"
    ]
    assert "is_test" in {column["name"] for column in inspector.get_columns("ai_assistant_conversations")}
    assert "activated_at" in {column["name"] for column in inspector.get_columns("ai_assistant_subscriptions")}
