"""
Appointment requests without a connected agenda: the half-days offered from the business hours, the
visitor's two wishes, and how the request, the email and the SMS carry them.

The model, the email sender, the SMS provider and the pushes are mocked; the database is an in-memory
SQLite. Routes are called directly. Business times are Paris; stored times naive UTC (UTC+2 in September).
"""

import asyncio
import importlib
import pkgutil
from datetime import date, datetime
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

import api.v1.routes.ai_assistants as routes
import migrations.add_ai_assistant_request_appointment_slots as slots_migration
import models
import services.ai_assistant.request_alerts as alerts_module
import services.ai_assistant.request_analyzer as analyzer_module
import services.ai_assistant.request_service as request_module
import services.email_sending_service as email_sending_module
import services.sms_service as sms_module
from core.database import Base
from enums.ai_assistant_request import AiAssistantDayPeriod, AiAssistantRequestType
from models.ai_assistant import AiAssistant
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from models.sms_config import SmsConfig
from schemas.ai_assistant import AiAssistantLeadRequest, AiAssistantSlotChoice
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots, AppointmentSlot
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.request_email import AiAssistantRequestEmail, RequestEmailContent
from services.ai_assistant.request_service import AiAssistantRequestService
from services.rate_limiter import SlidingWindowRateLimiter
from services.sms.gsm_segments import segment_count
from services.sms.sms_provider import SmsSendResult

for _module in pkgutil.iter_modules(models.__path__):
    importlib.import_module("models." + _module.name)

_VISITOR = Request({"type": "http", "headers": [], "client": ("203.0.113.9", 0)})
_MORNING = AiAssistantDayPeriod.MORNING
_AFTERNOON = AiAssistantDayPeriod.AFTERNOON
# A roofer's week: Tuesday afternoons and Thursday mornings only, closed on Wednesday and the weekend.
_HOURS = [
    {"day": "lundi", "hours": "08:00–12:00, 14:00–18:00"},
    {"day": "mardi", "hours": "14:00–18:00"},
    {"day": "mercredi", "hours": "Fermé"},
    {"day": "jeudi", "hours": "08:00–12:00"},
    {"day": "vendredi", "hours": "08:00–12:00, 14:00–18:00"},
    {"day": "samedi", "hours": "Fermé"},
    {"day": "dimanche", "hours": "Fermé"},
]
_SUNDAY = date(2026, 9, 20)
# Sunday 20 September 2026, 21:30 in Paris.
_SUNDAY_EVENING = datetime(2026, 9, 20, 21, 30)
# Tuesday 22 September 2026, 14:00 in Paris (12:00 UTC).
_TUESDAY_14H_UTC = datetime(2026, 9, 22, 12, 0)


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
    """Mock the model (it reads a quote), the email, the SMS provider and every push."""
    model = _Recorder({"type": "quote", "summary": "Fuite sous l'évier, veut un passage."})
    email = _Recorder({"success": True})
    provider = _Provider()
    monkeypatch.setattr(analyzer_module.assistant_llm_router, "complete_json", model)
    monkeypatch.setattr(email_sending_module.EmailSendingService, "send_via_user_identity", email)
    monkeypatch.setattr(request_module.notification_service, "notify_assistant_lead", _Recorder())
    monkeypatch.setattr(alerts_module.notification_service, "notify_assistant_requests_waiting", _Recorder())
    monkeypatch.setattr(sms_module.notification_service, "notify_sms_event", _Recorder())
    monkeypatch.setattr(sms_module.sms_service, "_provider", provider)
    monkeypatch.setattr(alerts_module, "_utc_now", lambda: _TUESDAY_14H_UTC)
    return {"model": model, "email": email, "sms": provider}


@pytest.fixture
def public_routes(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Fresh rate limits, Sunday evening in Paris, and the background follow-up recorded instead of run."""
    scheduled: list[int] = []
    monkeypatch.setattr(routes, "assistant_chat_limiter", SlidingWindowRateLimiter(30, 300))
    monkeypatch.setattr(routes, "assistant_lead_limiter", SlidingWindowRateLimiter(8, 300))
    monkeypatch.setattr(OpeningHoursCalendar, "business_now", staticmethod(lambda: _SUNDAY_EVENING))
    monkeypatch.setattr(routes.ai_assistant_request_service, "schedule_follow_up", scheduled.append)
    return scheduled


def _assistant(db: Session, *, status: str = "delivered", hours: list[dict[str, str]] | None = _HOURS) -> AiAssistant:
    prospect = ProspectDB(name="Plomberie Roux", category="Plombier", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Plomberie Roux", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.knowledge_json = {**(assistant.knowledge_json or {}), "opening_hours": hours}
    assistant.status = status
    assistant.email = "patron@plomberie-roux.fr"
    assistant.alert_phone_e164 = "+33612345678"
    if db.query(SmsConfig).filter(SmsConfig.user_id == 7).first() is None:
        db.add(SmsConfig(user_id=7, sender="Dibodev"))
    db.commit()
    return assistant


def _capture(
    db: Session, assistant: AiAssistant, slots: list[AppointmentSlot], **overrides: Any
) -> tuple[AiAssistantRequest, bool]:
    values: dict[str, Any] = {
        "name": "Julie Roux",
        "contact": "06 11 22 33 44",
        "need": "Fuite sous l'évier",
        "language": "fr",
        "session_id": "session-1",
        "appointment_slots": slots,
        "now": _SUNDAY_EVENING,
    }
    values.update(overrides)
    return AiAssistantRequestService().capture(db, assistant=assistant, **values)


def test_the_offer_follows_the_opening_hours_from_tomorrow() -> None:
    days = AiAssistantAppointmentSlots.offer(_HOURS, today=_SUNDAY)

    assert [(item.day, item.periods) for item in days] == [
        (date(2026, 9, 21), (_MORNING, _AFTERNOON)),
        (date(2026, 9, 22), (_AFTERNOON,)),
        (date(2026, 9, 24), (_MORNING,)),
        (date(2026, 9, 25), (_MORNING, _AFTERNOON)),
        (date(2026, 9, 28), (_MORNING, _AFTERNOON)),
        (date(2026, 9, 29), (_AFTERNOON,)),
    ]


def test_unknown_hours_offer_the_weekdays_and_unknown_days_fall_back_on_them() -> None:
    friday = date(2026, 9, 25)

    days = AiAssistantAppointmentSlots.offer(None, today=friday)
    partly_known = AiAssistantAppointmentSlots.offer(
        [{"day": name, "hours": "Fermé"} for name in ("lundi", "mardi")], today=friday
    )

    assert [item.day for item in days] == [date(2026, 9, day) for day in (28, 29, 30)] + [
        date(2026, 10, day) for day in (1, 2, 5)
    ]
    assert all(item.periods == (_MORNING, _AFTERNOON) for item in days)
    # Only Monday and Tuesday are known (closed); the other days stay unknown and fall back on the weekdays.
    assert date(2026, 9, 28) not in [item.day for item in partly_known]
    assert date(2026, 9, 30) in [item.day for item in partly_known]


def test_a_business_closed_all_week_offers_nothing() -> None:
    week = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")

    closed = AiAssistantAppointmentSlots.offer([{"day": name, "hours": "Fermé"} for name in week], today=_SUNDAY)

    assert closed == []


def test_the_check_keeps_two_offered_half_days_in_calendar_order() -> None:
    friday_morning = AppointmentSlot(day=date(2026, 9, 25), period=_MORNING)
    tuesday_afternoon = AppointmentSlot(day=date(2026, 9, 22), period=_AFTERNOON)

    kept = AiAssistantAppointmentSlots.check(_HOURS, [friday_morning, tuesday_afternoon, friday_morning], today=_SUNDAY)

    assert kept == [tuesday_afternoon, friday_morning]
    with pytest.raises(ValueError, match="Deux créneaux au plus"):
        AiAssistantAppointmentSlots.check(
            _HOURS,
            [friday_morning, tuesday_afternoon, AppointmentSlot(day=date(2026, 9, 21), period=_MORNING)],
            today=_SUNDAY,
        )
    for refused in (
        AppointmentSlot(day=date(2026, 9, 22), period=_MORNING),  # Tuesday opens at 14:00.
        AppointmentSlot(day=date(2026, 9, 23), period=_AFTERNOON),  # Closed on Wednesday.
        AppointmentSlot(day=_SUNDAY, period=_AFTERNOON),  # Never today.
        AppointmentSlot(day=date(2026, 10, 30), period=_MORNING),  # Past the offered days.
    ):
        with pytest.raises(ValueError, match="Ce créneau n'est plus proposé"):
            AiAssistantAppointmentSlots.check(_HOURS, [refused], today=_SUNDAY)


def test_labels_word_the_stored_half_days_and_skip_what_they_cannot_read() -> None:
    stored = [
        {"date": "2026-09-28", "period": "morning"},
        {"date": "2026-09-29", "period": "afternoon"},
        {"date": "demain", "period": "morning"},
        {"period": "evening"},
        "lundi",
    ]

    assert AiAssistantAppointmentSlots.labels(stored) == ["lun. 28/09, matin", "mar. 29/09, après-midi"]
    assert AiAssistantAppointmentSlots.labels(None) == []


def test_capture_stores_the_wished_half_days_and_refuses_one_no_longer_offered(db: Session) -> None:
    assistant = _assistant(db)
    wished = [
        AppointmentSlot(day=date(2026, 9, 25), period=_AFTERNOON),
        AppointmentSlot(day=date(2026, 9, 22), period=_AFTERNOON),
    ]

    request, created = _capture(db, assistant, wished)

    assert created
    assert request.type == AiAssistantRequestType.APPOINTMENT.value
    assert request.appointment_slots_json == [
        {"date": "2026-09-22", "period": "afternoon"},
        {"date": "2026-09-25", "period": "afternoon"},
    ]
    with pytest.raises(ValueError, match="Ce créneau n'est plus proposé"):
        _capture(db, assistant, [AppointmentSlot(day=date(2026, 9, 23), period=_MORNING)], session_id="session-2")
    assert db.query(AiAssistantRequest).count() == 1

    # The same visit leaving its details again keeps its wishes.
    again, created_again = _capture(db, assistant, [], contact="julie@example.fr")
    assert not created_again
    assert again.id == request.id
    assert again.appointment_slots_json == request.appointment_slots_json


def test_the_same_visit_adding_half_days_turns_its_request_into_an_appointment(db: Session) -> None:
    assistant = _assistant(db)
    first, _ = _capture(db, assistant, [])
    first.type = AiAssistantRequestType.QUESTION.value
    db.commit()

    again, created = _capture(db, assistant, [AppointmentSlot(day=date(2026, 9, 24), period=_MORNING)])

    assert not created
    assert again.id == first.id
    assert again.type == AiAssistantRequestType.APPOINTMENT.value
    assert again.appointment_slots_json == [{"date": "2026-09-24", "period": "morning"}]


def test_the_follow_up_makes_it_an_appointment_announced_with_its_half_days(
    db: Session, outbox: dict[str, Any]
) -> None:
    assistant = _assistant(db)
    request, _ = _capture(db, assistant, [AppointmentSlot(day=date(2026, 9, 22), period=_AFTERNOON)])
    request.created_at = _TUESDAY_14H_UTC
    db.commit()

    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    assert request.type == AiAssistantRequestType.APPOINTMENT.value
    sent = outbox["email"].calls[0]
    assert sent["subject"].startswith("Demande de rendez-vous — Julie Roux")
    assert "Créneaux souhaités (à confirmer)" in sent["body_html"]
    assert "mar. 22/09, après-midi" in sent["body_html"]
    [sms] = outbox["sms"].texts
    assert segment_count(sms) == 1
    assert "Julie Roux, 06 11 22 33 44, pour mar. 22/09 après-midi : Fuite sous l'évier" in sms


def test_an_urgency_read_by_the_analysis_wins_over_the_half_days(db: Session, outbox: dict[str, Any]) -> None:
    outbox["model"].result = {"type": "urgent", "summary": "Fuite sous l'évier, ça coule."}
    assistant = _assistant(db)
    request, _ = _capture(db, assistant, [AppointmentSlot(day=date(2026, 9, 22), period=_AFTERNOON)])
    request.created_at = _TUESDAY_14H_UTC
    db.commit()

    asyncio.run(AiAssistantRequestService().follow_up(db, request, assistant))

    assert request.type == AiAssistantRequestType.URGENT.value
    [sms] = outbox["sms"].texts
    assert sms.startswith("URGENT, nouvelle demande de Julie Roux, 06 11 22 33 44, pour mar. 22/09 après-midi")


_LINK = "demo.dibodev.fr/client/1234.tneuo0.K4lzdHZLLanlAxWK"
_SLOTS = ("mar. 22/09 après-midi", "ven. 25/09 matin")
_LONG_SUMMARY = (
    "Fuite sous l'évier de la cuisine depuis ce matin, le meuble commence à gonfler, elle voudrait un passage "
    "rapide et un devis pour remplacer le siphon et le flexible."
)


def test_the_sms_keeps_both_half_days_whole_whatever_the_summary_and_the_link() -> None:
    for name in ("Julie Roux", "Jean-Christophe Dupont-Lefebvre de la Tour"):
        text = alerts_module.AlertSms.new_request(
            request_type=AiAssistantRequestType.APPOINTMENT,
            name=name,
            contact="06 11 22 33 44",
            summary=_LONG_SUMMARY,
            has_photos=False,
            link=_LINK,
        )
        with_slots = alerts_module.AlertSms.new_request(
            request_type=AiAssistantRequestType.APPOINTMENT,
            name=name,
            contact="06 11 22 33 44",
            summary=_LONG_SUMMARY,
            has_photos=False,
            link=_LINK,
            slots=_SLOTS,
        )

        assert segment_count(text) == 1
        assert segment_count(with_slots) == 1
        assert "06 11 22 33 44, pour mar. 22/09 après-midi ou ven. 25/09 matin" in with_slots

    reminder = alerts_module.AlertSms.reminder(
        request_type=AiAssistantRequestType.APPOINTMENT,
        name="Julie Roux",
        contact="06 11 22 33 44",
        summary=_LONG_SUMMARY,
        received_local=datetime(2026, 9, 21, 9, 0),
        link=_LINK,
        slots=_SLOTS,
    )
    assert segment_count(reminder) == 1
    assert "pour mar. 22/09 après-midi ou ven. 25/09 matin" in reminder


def test_a_contact_too_long_for_both_half_days_keeps_the_first_one_or_none() -> None:
    long_contact = "julie.roux.plomberie.chauffage@entreprise-exemple-longue.fr"

    text = alerts_module.AlertSms.new_request(
        request_type=AiAssistantRequestType.QUOTE,
        name="Jean-Christophe Dupont-Lefebvre de la Tour",
        contact=long_contact,
        summary=_LONG_SUMMARY,
        has_photos=True,
        link=_LINK,
        slots=_SLOTS,
    )

    assert segment_count(text) == 1
    assert long_contact in text
    assert "pour mar. 22/09 après-midi" in text
    assert "ven. 25/09 matin" not in text
    # A head that cannot even take one half-day goes without (the email has them).
    no_room = alerts_module.AlertSms.reminder(
        request_type=AiAssistantRequestType.APPOINTMENT,
        name="Jean-Christophe Dupont-Lefebvre de la Tour",
        contact=long_contact,
        summary=None,
        received_local=datetime(2026, 9, 21, 9, 0),
        slots=_SLOTS,
    )
    assert segment_count(no_room) == 1
    assert long_contact in no_room


def test_the_email_lists_the_wished_half_days() -> None:
    rendered = AiAssistantRequestEmail.render(
        RequestEmailContent(
            business_name="Plomberie Roux",
            assistant_name="Léa",
            request_type=AiAssistantRequestType.APPOINTMENT,
            visitor_name="Julie <Roux>",
            contact="06 11 22 33 44",
            need="Fuite sous l'évier",
            need_summary="Fuite sous l'évier, veut un passage.",
            received_at=datetime(2026, 9, 20, 19, 30),
            received_outside_hours=True,
            transcript=[],
            handled_url="https://api.example.fr/handled",
            appointment_slots=("mar. 22/09, après-midi", "ven. 25/09, matin"),
        )
    )

    assert "Créneaux souhaités (à confirmer)" in rendered.html
    assert "mar. 22/09, après-midi<br/>ven. 25/09, matin" in rendered.html
    assert "Julie &lt;Roux&gt;" in rendered.html


def test_the_public_slots_route_serves_the_offer(db: Session, public_routes: list[int]) -> None:
    assistant = _assistant(db, status="active")

    offer = asyncio.run(routes.get_assistant_appointment_slots(assistant.slug, _VISITOR, after=None, db=db))

    assert offer.max_chosen == 2
    assert [(item.date, item.periods) for item in offer.days][:2] == [
        (date(2026, 9, 21), [_MORNING, _AFTERNOON]),
        (date(2026, 9, 22), [_AFTERNOON]),
    ]
    with pytest.raises(HTTPException) as missing:
        asyncio.run(routes.get_assistant_appointment_slots("inconnu", _VISITOR, after=None, db=db))
    assert missing.value.status_code == 404


def test_the_lead_route_takes_the_half_days_and_answers_422_for_one_withdrawn(
    db: Session, public_routes: list[int]
) -> None:
    assistant = _assistant(db, status="active")
    payload = AiAssistantLeadRequest(
        name="Julie Roux",
        contact="06 11 22 33 44",
        session_id="session-1",
        slots=[AiAssistantSlotChoice(date=date(2026, 9, 21), period=_MORNING)],
    )

    asyncio.run(routes.submit_assistant_lead(assistant.slug, payload, _VISITOR, db))

    [stored] = db.query(AiAssistantRequest).all()
    assert stored.appointment_slots_json == [{"date": "2026-09-21", "period": "morning"}]
    assert public_routes == [stored.id]

    withdrawn = payload.model_copy(
        update={"session_id": "session-2", "slots": [AiAssistantSlotChoice(date=date(2026, 9, 23), period=_MORNING)]}
    )
    with pytest.raises(HTTPException) as refused:
        asyncio.run(routes.submit_assistant_lead(assistant.slug, withdrawn, _VISITOR, db))
    assert refused.value.status_code == 422
    assert refused.value.detail == "Ce créneau n'est plus proposé"
    assert db.query(AiAssistantRequest).count() == 1


def test_the_lead_payload_takes_two_half_days_at_most() -> None:
    choice = {"date": "2026-09-21", "period": "morning"}

    with pytest.raises(ValueError):
        AiAssistantLeadRequest(name="Julie", contact="06 11 22 33 44", slots=[choice, choice, choice])
    with pytest.raises(ValueError):
        AiAssistantLeadRequest(
            name="Julie", contact="06 11 22 33 44", slots=[{"date": "2026-09-21", "period": "night"}]
        )


def test_the_migration_adds_the_column_once(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE ai_assistant_requests (id INTEGER PRIMARY KEY, name VARCHAR(120))"))
        conn.commit()
    monkeypatch.setattr(slots_migration, "engine", engine)

    slots_migration.run_migration()
    slots_migration.run_migration()

    columns = {column["name"] for column in inspect(engine).get_columns("ai_assistant_requests")}
    assert "appointment_slots_json" in columns
