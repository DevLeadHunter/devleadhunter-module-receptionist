"""The receptionist's notifications: tagged with their module, and filed on a prospect only when there is one."""

import asyncio
from typing import Any

import pytest
from sqlalchemy.orm import Session

import services.notification_service as notification_module
import services.sms_service as sms_module
from enums.sms_message_kind import SmsMessageKind
from models.sms_config import SmsConfig
from models.sms_message import SmsMessage
from services.notification_service import notification_service
from services.sms.sms_provider import SmsSendResult
from services.sms_service import SmsService
from tests.assistant_fakes import AsyncCallRecorder

# The receptionist's notifications about a subscriber or a demo, with what each one needs besides the prospect.
_ASSISTANT_NOTIFICATIONS: list[tuple[str, dict[str, Any]]] = [
    ("notify_assistant_subscription", {"amount_cents": 7900, "interval": "month"}),
    ("notify_assistant_lead", {"lead_name": "Julie Roux", "need": "Fuite sous l'évier"}),
    ("notify_assistant_requests_waiting", {"waiting_count": 2}),
    ("notify_assistant_inactive", {"month_label": "septembre 2026"}),
    ("notify_assistant_interest", {"message": "Rappelez-moi"}),
]


class _RefusingProvider:
    """A configured SMS provider that refuses every message."""

    is_configured = True

    async def send(self, **_: Any) -> SmsSendResult:
        return SmsSendResult(success=False, error="Numéro injoignable")


@pytest.fixture
def written(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict[str, Any]]]:
    """The activity log entries and the pushes the notifications write."""
    calls: dict[str, list[dict[str, Any]]] = {"log": [], "push": []}

    async def dispatch(**kwargs: Any) -> None:
        calls["push"].append(kwargs)

    monkeypatch.setattr(
        notification_module.activity_log_service, "record", lambda **kwargs: calls["log"].append(kwargs)
    )
    monkeypatch.setattr(notification_service, "_dispatch", dispatch)
    return calls


@pytest.mark.parametrize(("method_name", "details"), _ASSISTANT_NOTIFICATIONS)
def test_an_assistant_notification_without_a_prospect_points_to_no_prospect(
    db: Session, written: dict[str, list[dict[str, Any]]], method_name: str, details: dict[str, Any]
) -> None:
    notify = getattr(notification_service, method_name)

    asyncio.run(notify(db, user_id=7, prospect_id=None, fallback_name="Garage Martin", **details))

    [entry] = written["log"]
    assert (entry["entity_type"], entry["entity_id"]) == (None, None)


@pytest.mark.parametrize(("method_name", "details"), _ASSISTANT_NOTIFICATIONS)
def test_an_assistant_notification_about_a_prospect_points_to_it(
    db: Session, written: dict[str, list[dict[str, Any]]], method_name: str, details: dict[str, Any]
) -> None:
    notify = getattr(notification_service, method_name)

    asyncio.run(notify(db, user_id=7, prospect_id=5, fallback_name="Garage Martin", **details))

    [entry] = written["log"]
    assert (entry["entity_type"], entry["entity_id"]) == ("prospect", 5)


def test_a_receptionist_sms_push_names_its_module(db: Session, written: dict[str, list[dict[str, Any]]]) -> None:
    asyncio.run(
        notification_service.notify_sms_event(
            db, user_id=7, event_name="sms_failed", fallback_name="Rendez-vous Garage Morel", is_assistant_module=True
        )
    )
    asyncio.run(notification_service.notify_sms_event(db, user_id=7, event_name="sms_sent", fallback_name="06"))

    receptionist, site = written["push"]
    assert receptionist["body"] == "🤖 Assistant IA · Échec de l'envoi du SMS"
    assert site["body"] == "SMS envoyé"


@pytest.mark.parametrize(
    ("body", "kind", "is_receptionist"),
    [
        ("Bonjour, mon assistant : demo.dibodev.fr/s/ia/garage-martin Léo STOP au 36180", None, True),
        ("Bonjour, la vidéo de mon email : demo.dibodev.fr/s/va/garage-martin Léo STOP au 36180", None, True),
        ("Bonjour, j'ai préparé votre site : demo.dibodev.fr/s/garage-martin Léo STOP au 36180", None, False),
        ("Bonjour, en 30 s de vidéo : demo.dibodev.fr/s/v/garage-martin Léo STOP au 36180", None, False),
        ("Bonjour, le site de IA : demo.dibodev.fr/s/ia Léo STOP au 36180", None, False),
        ("Nouvelle demande de devis de Marc, 06 11 22 33 44", SmsMessageKind.SERVICE.value, True),
    ],
)
def test_an_sms_belongs_to_the_receptionist_by_its_kind_or_its_link(
    body: str, kind: str | None, is_receptionist: bool
) -> None:
    message = SmsMessage(user_id=7, to_e164="+33611223344", sender="Dibodev", body=body, kind=kind)

    assert SmsService.is_assistant_message(message) is is_receptionist


def test_a_failed_service_sms_is_notified_under_the_receptionist(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    notified = AsyncCallRecorder()
    monkeypatch.setattr(sms_module.notification_service, "notify_sms_event", notified)
    config = SmsConfig(user_id=7, sender="Dibodev")
    db.add(config)
    db.commit()

    outcome = asyncio.run(
        SmsService(provider=_RefusingProvider()).send_service_message(
            db, user_id=7, config=config, to_e164="+33611223344", text="Nouvelle demande", recipient_name="Garage"
        )
    )

    assert not outcome.sent
    [call] = notified.calls
    assert call["event_name"] == "sms_failed" and call["is_assistant_module"] is True
