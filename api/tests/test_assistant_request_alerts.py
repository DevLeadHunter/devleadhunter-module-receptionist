"""
Owner alerts of the assistant requests: channels per type, the night window, one reminder, the 48 h warning.

The model, the email sender, the SMS provider and the pushes are mocked; the database is an in-memory
SQLite. Times are naive UTC, the business is in Paris (UTC+2 in September).
"""

import asyncio
import importlib
import pkgutil
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import migrations.add_ai_assistant_alerts as alerts_migration
import models
import services.ai_assistant.request_alerts as alerts_module
import services.ai_assistant.request_analyzer as analyzer_module
import services.ai_assistant.request_service as request_module
import services.email_sending_service as email_sending_module
import services.sms_service as sms_module
from core.database import Base
from enums.ai_assistant_request import AiAssistantRequestStatus, AiAssistantRequestType
from models.ai_assistant import AiAssistant
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from models.sms_config import SmsConfig
from models.sms_message import SmsMessage
from models.sms_suppression import SmsSuppression
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.request_alerts import AiAssistantRequestAlerts, AlertSettings, AlertSms, QuietHours
from services.ai_assistant.request_service import AiAssistantRequestService
from services.sms.gsm_segments import segment_count
from services.sms.phone_normalizer import to_e164_mobile
from services.sms.sms_provider import SmsSendResult
from services.sms_automation_service import SmsAutomationService

for _module in pkgutil.iter_modules(models.__path__):
    importlib.import_module("models." + _module.name)

# 22:00 in Paris on Monday 21 September 2026 (CEST, UTC+2).
_MONDAY_22H_UTC = datetime(2026, 9, 21, 20, 0)
_TUESDAY_8H_UTC = datetime(2026, 9, 22, 6, 0)


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(engine) -> Session:
    session = sessionmaker(bind=engine)()
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


class _Provider:
    """A configured SMS provider that accepts everything."""

    is_configured = True

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def send(self, *, to_e164: str, sender: str, text: str, **_: Any) -> SmsSendResult:
        self.texts.append(text)
        return SmsSendResult(success=True, provider_message_id=f"m{len(self.texts)}", price_cents=6)


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mock the model (a quote), the email, the SMS provider and every push."""
    model = _Recorder({"type": "quote", "summary": "Tuiles déplacées côté rue, devis demandé."})
    email = _Recorder({"success": True})
    push = _Recorder()
    waiting = _Recorder()
    sms_event = _Recorder()
    provider = _Provider()
    monkeypatch.setattr(analyzer_module.assistant_llm_router, "complete_json", model)
    monkeypatch.setattr(email_sending_module.EmailSendingService, "send_via_user_identity", email)
    monkeypatch.setattr(request_module.notification_service, "notify_assistant_lead", push)
    monkeypatch.setattr(alerts_module.notification_service, "notify_assistant_requests_waiting", waiting)
    monkeypatch.setattr(sms_module.notification_service, "notify_sms_event", sms_event)
    monkeypatch.setattr(sms_module.sms_service, "_provider", provider)
    return {"model": model, "email": email, "push": push, "waiting": waiting, "sms_event": sms_event, "sms": provider}


def _assistant(
    db: Session,
    *,
    status: str = "delivered",
    phone: str | None = "+33612345678",
    sender: str = "Dibodev",
    **alert_fields: Any,
) -> AiAssistant:
    prospect = ProspectDB(name="Toitures Morel", category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Toitures Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = status
    assistant.email = "patron@toitures-morel.fr"
    assistant.alert_phone_e164 = phone
    for field, value in alert_fields.items():
        setattr(assistant, field, value)
    if sender and db.query(SmsConfig).filter(SmsConfig.user_id == 7).first() is None:
        db.add(SmsConfig(user_id=7, sender=sender))
    db.commit()
    return assistant


def _request(db: Session, assistant: AiAssistant, *, created_at: datetime, **fields: Any) -> AiAssistantRequest:
    request = AiAssistantRequest(
        user_id=assistant.user_id,
        prospect_id=assistant.prospect_id,
        assistant_id=assistant.id,
        name="Marc Dubois",
        contact="06 98 76 54 32",
        need="Des tuiles ont bougé avec le vent, il me faudrait un devis",
        created_at=created_at,
        **fields,
    )
    db.add(request)
    db.commit()
    return request


def _freeze(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    monkeypatch.setattr(alerts_module, "_utc_now", lambda: moment)


def test_settings_default_to_sms_for_what_cannot_wait_and_a_night_window(db: Session) -> None:
    assistant = _assistant(db, phone=None)

    settings = AlertSettings.of(assistant)

    assert (settings.sms_enabled, settings.email_enabled) == (True, True)
    assert settings.sms_types == {
        AiAssistantRequestType.QUOTE,
        AiAssistantRequestType.APPOINTMENT,
        AiAssistantRequestType.URGENT,
    }
    assert (settings.quiet_start_hour, settings.quiet_end_hour) == (22, 8)
    assert not settings.wants_sms(AiAssistantRequestType.QUOTE)

    assistant.alert_phone_e164 = "+33612345678"
    settings = AlertSettings.of(assistant)
    assert settings.wants_sms(AiAssistantRequestType.QUOTE)
    assert not settings.wants_sms(AiAssistantRequestType.QUESTION)


def test_the_alert_number_must_be_able_to_receive_an_sms() -> None:
    assert to_e164_mobile("06 12 34 56 78") == "+33612345678"
    assert to_e164_mobile("+33 (0)7 12 34 56 78") == "+33712345678"
    assert to_e164_mobile("+352 621 123 456", country="LU") == "+352621123456"
    assert to_e164_mobile("0032 470 12 34 56", country="BE") == "+32470123456"
    assert to_e164_mobile("01 23 45 67 89") is None
    assert to_e164_mobile("+33 1 23 45 67 89") is None
    assert to_e164_mobile("+12") is None
    assert to_e164_mobile("  ") is None


def test_a_foreign_mobile_typed_without_its_country_code_is_never_read_as_french() -> None:
    assert to_e164_mobile("621 123 456", country="LU") is None
    assert to_e164_mobile("079 123 45 67", country="CH") is None
    assert to_e164_mobile("06 12 34 56 78", country="BE") is None
    assert to_e164_mobile("612 345 678") is None


def test_quiet_hours_hold_until_the_end_of_the_window() -> None:
    evening = datetime(2026, 9, 21, 23, 15)
    night = datetime(2026, 9, 22, 2, 0)
    noon = datetime(2026, 9, 22, 12, 0)

    assert QuietHours.release_at(evening, 22, 8) == datetime(2026, 9, 22, 8, 0)
    assert QuietHours.release_at(night, 22, 8) == datetime(2026, 9, 22, 8, 0)
    assert QuietHours.release_at(noon, 22, 8) == noon
    assert QuietHours.contains(datetime(2026, 9, 22, 12, 30), 12, 14)
    assert not QuietHours.contains(datetime(2026, 9, 22, 14, 0), 12, 14)
    assert not QuietHours.contains(night, 8, 8)


def test_the_alert_sms_fits_one_segment_and_keeps_the_contact_whole() -> None:
    text = AlertSms.new_request(
        request_type=AiAssistantRequestType.QUOTE,
        name="Françoise 🙂 de la Boulangerie",
        contact="francoise.martin@boulangerie-du-centre.fr",
        summary="Rayure profonde sur la portière avant gauche après un accrochage sur le parking, "
        "elle voudrait un devis pour une reprise de peinture et savoir si c'est possible cette semaine.",
        has_photos=True,
    )

    assert segment_count(text) == 1
    assert text.startswith("Nouvelle demande de devis (photo) de Francoise de la Boulangerie, ")
    assert "francoise.martin@boulangerie-du-centre.fr : Rayure profonde" in text
    assert text.endswith("...")


def test_the_final_period_never_pushes_an_alert_sms_to_two_segments() -> None:
    head_and_contact = "Nouvelle demande de devis de Marc Dubois, 06 98 76 54 32"
    summary = "x" * (160 - len(head_and_contact) - len(" : "))

    text = AlertSms.new_request(
        request_type=AiAssistantRequestType.QUOTE,
        name="Marc Dubois",
        contact="06 98 76 54 32",
        summary=summary,
        has_photos=False,
    )

    assert segment_count(text) == 1


def test_a_quote_at_22h_pushes_now_texts_at_8h_and_reminds_once_the_next_day(
    db: Session, outbox: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    request = _request(db, assistant, created_at=_MONDAY_22H_UTC)
    alerts = AiAssistantRequestAlerts()
    _freeze(monkeypatch, _MONDAY_22H_UTC)

    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    assert len(outbox["push"].calls) == 1
    assert len(outbox["email"].calls) == 1
    assert outbox["sms"].texts == []
    assert request.sms_due_at == _TUESDAY_8H_UTC

    assert asyncio.run(alerts.send_due_sms(db, now=_TUESDAY_8H_UTC - timedelta(minutes=1))) == 0
    assert asyncio.run(alerts.send_due_sms(db, now=_TUESDAY_8H_UTC + timedelta(minutes=3))) == 1
    assert asyncio.run(alerts.send_due_sms(db, now=_TUESDAY_8H_UTC + timedelta(minutes=8))) == 0
    assert len(outbox["sms"].texts) == 1
    assert outbox["sms"].texts[0].startswith("Nouvelle demande de devis de Marc Dubois, 06 98 76 54 32 : ")
    assert "STOP" not in outbox["sms"].texts[0]
    assert outbox["sms_event"].calls == []

    # Tuesday 22:00 Paris is a day later but in the night window: the reminder waits for 8:00.
    tuesday_22h = _MONDAY_22H_UTC + timedelta(hours=24)
    assert asyncio.run(alerts.send_reminders(db, now=tuesday_22h - timedelta(hours=1))) == 0
    assert asyncio.run(alerts.send_reminders(db, now=tuesday_22h)) == 0
    assert asyncio.run(alerts.send_reminders(db, now=tuesday_22h + timedelta(hours=10))) == 1
    assert asyncio.run(alerts.send_reminders(db, now=tuesday_22h + timedelta(hours=11))) == 0

    assert len(outbox["sms"].texts) == 2
    assert outbox["sms"].texts[1].startswith("Rappel, en attente depuis le 21/09 : demande de devis de Marc Dubois")
    assert len(outbox["email"].calls) == 2
    assert outbox["email"].calls[1]["subject"].startswith("Rappel : Demande de devis")
    assert db.query(SmsMessage).filter(SmsMessage.prospect_id.is_(None)).count() == 2


def test_a_question_goes_by_email_only(db: Session, outbox: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    outbox["model"].result = {"type": "question", "summary": "Demande si le couvreur intervient à Metz."}
    assistant = _assistant(db)
    request = _request(db, assistant, created_at=_TUESDAY_8H_UTC + timedelta(hours=4))
    _freeze(monkeypatch, _TUESDAY_8H_UTC + timedelta(hours=4))

    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    assert len(outbox["email"].calls) == 1
    assert request.sms_due_at is None
    assert outbox["sms"].texts == []


def test_a_quote_in_the_day_is_texted_at_once(
    db: Session, outbox: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    request = _request(db, assistant, created_at=_TUESDAY_8H_UTC + timedelta(hours=4))
    _freeze(monkeypatch, _TUESDAY_8H_UTC + timedelta(hours=4))

    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    assert len(outbox["sms"].texts) == 1
    assert request.sms_sent_at is not None


def test_a_demo_never_alerts_its_prospect(db: Session, outbox: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    assistant = _assistant(db, status="active")
    request = _request(db, assistant, created_at=_TUESDAY_8H_UTC + timedelta(hours=4))
    _freeze(monkeypatch, _TUESDAY_8H_UTC + timedelta(hours=4))

    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    assert len(outbox["push"].calls) == 1
    assert outbox["email"].calls == []
    assert outbox["sms"].texts == []
    assert request.sms_due_at is None


def test_the_owner_can_turn_each_channel_off(
    db: Session, outbox: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db, alert_sms_enabled=False, alert_email_enabled=False)
    request = _request(db, assistant, created_at=_TUESDAY_8H_UTC + timedelta(hours=4))
    _freeze(monkeypatch, _TUESDAY_8H_UTC + timedelta(hours=4))

    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    assert outbox["email"].calls == []
    assert outbox["sms"].texts == []
    assert len(outbox["push"].calls) == 1


def test_a_request_handled_before_8h_is_never_texted(
    db: Session, outbox: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    request = _request(db, assistant, created_at=_MONDAY_22H_UTC)
    _freeze(monkeypatch, _MONDAY_22H_UTC)
    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    AiAssistantRequestService().update_for_owner(db, request, status=AiAssistantRequestStatus.HANDLED)

    assert asyncio.run(AiAssistantRequestAlerts().send_due_sms(db, now=_TUESDAY_8H_UTC + timedelta(minutes=2))) == 0
    assert outbox["sms"].texts == []


def test_requests_waiting_48h_warn_the_operator_once_per_subscriber(db: Session, outbox: dict[str, Any]) -> None:
    subscriber = _assistant(db)
    demo = _assistant(db, status="active")
    alerted = {"owner_notified_at": _MONDAY_22H_UTC, "owner_alerted_at": _MONDAY_22H_UTC}
    _request(db, subscriber, created_at=_MONDAY_22H_UTC, **alerted)
    _request(db, subscriber, created_at=_MONDAY_22H_UTC + timedelta(hours=1), **alerted)
    _request(db, subscriber, created_at=_MONDAY_22H_UTC, is_test=True, **alerted)
    # Left on the demo before the sale: only the operator heard of it, it is not the owner's backlog.
    _request(db, subscriber, created_at=_MONDAY_22H_UTC, owner_notified_at=_MONDAY_22H_UTC)
    _request(db, demo, created_at=_MONDAY_22H_UTC, owner_notified_at=_MONDAY_22H_UTC)
    alerts = AiAssistantRequestAlerts()
    later = _MONDAY_22H_UTC + timedelta(hours=49)

    assert asyncio.run(alerts.notify_operator_of_waiting_requests(db, now=later - timedelta(hours=2))) == 0
    assert asyncio.run(alerts.notify_operator_of_waiting_requests(db, now=later)) == 2
    assert asyncio.run(alerts.notify_operator_of_waiting_requests(db, now=later + timedelta(hours=1))) == 0

    assert len(outbox["waiting"].calls) == 1
    assert outbox["waiting"].calls[0]["waiting_count"] == 2
    assert outbox["waiting"].calls[0]["prospect_id"] == subscriber.prospect_id


def test_a_demo_request_is_never_reminded_after_the_sale(db: Session, outbox: dict[str, Any]) -> None:
    assistant = _assistant(db, status="active")
    request = _request(db, assistant, created_at=_MONDAY_22H_UTC)
    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))
    assistant.status = "delivered"
    db.commit()

    reminded = asyncio.run(AiAssistantRequestAlerts().send_reminders(db, now=_MONDAY_22H_UTC + timedelta(hours=34)))

    assert reminded == 0
    assert outbox["email"].calls == [] and outbox["sms"].texts == []
    assert request.owner_notified_at is not None and request.owner_alerted_at is None


def test_a_request_handled_after_a_pass_loaded_it_is_left_alone(db: Session) -> None:
    assistant = _assistant(db)
    request = _request(db, assistant, created_at=_MONDAY_22H_UTC)
    request.status = AiAssistantRequestStatus.HANDLED.value
    db.commit()

    assert not AiAssistantRequestAlerts.claim(db, request, AiAssistantRequest.reminder_sent_at)
    assert request.reminder_sent_at is None


def test_the_service_sms_is_one_segment_without_stop_and_honours_the_stop_list(
    db: Session, outbox: dict[str, Any]
) -> None:
    config = SmsConfig(user_id=7, sender="Dibodev")
    db.add(config)
    db.commit()
    service = sms_module.sms_service

    sent = asyncio.run(
        service.send_service_message(
            db, user_id=7, config=config, to_e164="+33612345678", text="Nouvelle demande.", recipient_name="X"
        )
    )
    too_long = asyncio.run(
        service.send_service_message(
            db, user_id=7, config=config, to_e164="+33612345678", text="a" * 161, recipient_name="X"
        )
    )
    db.add(SmsSuppression(user_id=7, phone_e164="+33612345678", reason="stop"))
    db.commit()
    stopped = asyncio.run(
        service.send_service_message(
            db, user_id=7, config=config, to_e164="+33612345678", text="Nouvelle demande.", recipient_name="X"
        )
    )

    assert sent.sent and outbox["sms"].texts == ["Nouvelle demande."]
    assert sent.message is not None and sent.message.prospect_id is None
    assert sent.message.kind == "service"
    assert SmsAutomationService()._sent_today(db, 7) == 0
    assert not too_long.sent and not stopped.sent
    assert outbox["sms_event"].calls == []


def test_alert_settings_are_saved_only_with_a_number_that_can_receive_an_sms(db: Session) -> None:
    assistant = _assistant(db, phone=None)

    with pytest.raises(ValueError):
        ai_assistant_service.update(db, assistant, {"alert_phone": "01 23 45 67 89", "alert_sms_enabled": False})
    assert assistant.alert_sms_enabled is None

    ai_assistant_service.update(
        db,
        assistant,
        {
            "alert_phone": "06 12 34 56 78",
            "alert_sms_types": [AiAssistantRequestType.URGENT, AiAssistantRequestType.QUOTE],
            "alert_quiet_start_hour": 21,
            "alert_quiet_end_hour": 7,
        },
    )

    assert assistant.alert_phone_e164 == "+33612345678"
    assert assistant.alert_sms_types == ["quote", "urgent"]
    assert (assistant.alert_quiet_start_hour, assistant.alert_quiet_end_hour) == (21, 7)
    ai_assistant_service.update(db, assistant, {"alert_phone": ""})
    assert assistant.alert_phone_e164 is None


def test_the_migration_adds_the_missing_alert_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE ai_assistants (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE ai_assistant_requests (id INTEGER PRIMARY KEY, sms_due_at DATETIME)"))
        conn.execute(text("CREATE TABLE sms_messages (id INTEGER PRIMARY KEY)"))
        conn.commit()
    monkeypatch.setattr(alerts_migration, "engine", engine)

    alerts_migration.run_migration()
    alerts_migration.run_migration()

    inspector = inspect(engine)
    assistant_columns = {column["name"] for column in inspector.get_columns("ai_assistants")}
    request_columns = {column["name"] for column in inspector.get_columns("ai_assistant_requests")}
    assert {"alert_phone_e164", "alert_sms_types", "alert_quiet_end_hour"} <= assistant_columns
    assert {"owner_alerted_at", "sms_due_at", "sms_sent_at", "reminder_sent_at", "stale_notified_at"} <= request_columns
    assert "kind" in {column["name"] for column in inspector.get_columns("sms_messages")}
