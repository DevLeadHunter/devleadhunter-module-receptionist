"""
What the receptionist's outgoing messages share: the one-shot claim, the service SMS, the operator's journal.

The SMS provider and the activity log are mocked; the database is an in-memory SQLite.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

import services.ai_assistant.message_delivery as delivery_module
import services.sms_service as sms_module
from enums.ai_assistant_request import AiAssistantRequestStatus
from enums.sms_message_kind import SmsMessageKind
from models.ai_assistant import AiAssistant
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from models.sms_config import SmsConfig
from models.sms_message import SmsMessage
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.message_delivery import AiAssistantMessageDelivery
from tests.assistant_fakes import AcceptingSmsProvider, AsyncCallRecorder

_MOMENT = datetime(2026, 9, 22, 12, 0)


def _assistant(db: Session) -> AiAssistant:
    prospect = ProspectDB(name="Toitures Morel", category="Couvreur", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    return ai_assistant_service.create(
        db, user_id=7, business_name="Toitures Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )


def _request(db: Session, assistant: AiAssistant, **fields: Any) -> AiAssistantRequest:
    request = AiAssistantRequest(
        user_id=7, prospect_id=assistant.prospect_id, assistant_id=assistant.id, name="Marc", contact="06", **fields
    )
    db.add(request)
    db.commit()
    return request


def test_a_one_shot_message_is_claimed_once_and_its_row_refreshed(db: Session) -> None:
    request = _request(db, _assistant(db))
    unsent = AiAssistantRequest.sms_sent_at.is_(None)

    first = AiAssistantMessageDelivery.claim(db, request, unsent, values={AiAssistantRequest.sms_sent_at: _MOMENT})
    again = AiAssistantMessageDelivery.claim(db, request, unsent, values={AiAssistantRequest.sms_sent_at: _MOMENT})

    assert (first, again) == (True, False)
    assert request.sms_sent_at == _MOMENT


def test_a_claim_leaves_alone_a_row_whose_conditions_no_longer_hold(db: Session) -> None:
    request = _request(db, _assistant(db), status=AiAssistantRequestStatus.HANDLED.value)

    claimed = AiAssistantMessageDelivery.claim(
        db,
        request,
        AiAssistantRequest.status == AiAssistantRequestStatus.NEW.value,
        AiAssistantRequest.reminder_sent_at.is_(None),
        values={AiAssistantRequest.reminder_sent_at: _MOMENT},
    )

    assert not claimed
    assert request.reminder_sent_at is None


def test_a_report_attempt_is_counted_by_one_pass_only(db: Session) -> None:
    assistant = _assistant(db)
    report = AiAssistantReport(user_id=7, prospect_id=assistant.prospect_id, assistant_id=assistant.id, month="2026-09")
    db.add(report)
    db.commit()
    seen_attempts = report.attempts

    def count_attempt() -> bool:
        return AiAssistantMessageDelivery.claim(
            db,
            report,
            AiAssistantReport.attempts == seen_attempts,
            values={
                AiAssistantReport.attempts: AiAssistantReport.attempts + 1,
                AiAssistantReport.last_attempt_at: _MOMENT,
            },
        )

    assert count_attempt()
    assert not count_attempt()
    assert (report.attempts, report.last_attempt_at) == (1, _MOMENT)


def test_a_service_sms_leaves_through_the_operator_sender(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AcceptingSmsProvider()
    monkeypatch.setattr(sms_module.sms_service, "_provider", provider)
    monkeypatch.setattr(sms_module.notification_service, "notify_sms_event", AsyncCallRecorder())
    assistant = _assistant(db)
    config = SmsConfig(user_id=7, sender="Dibodev")
    db.add(config)
    db.commit()

    outcome = asyncio.run(
        AiAssistantMessageDelivery.send_service_sms(
            db,
            assistant,
            config,
            to_e164="+33612345678",
            text="Rappel : rendez-vous demain, 14:00, chez Toitures Morel.",
            recipient_name="Rendez-vous Toitures Morel",
            log_label="Appointment 1 SMS",
        )
    )

    assert outcome is not None and outcome.sent
    assert provider.texts == ["Rappel : rendez-vous demain, 14:00, chez Toitures Morel."]
    [message] = db.query(SmsMessage).all()
    assert (message.kind, message.recipient_name) == (SmsMessageKind.SERVICE.value, "Rendez-vous Toitures Morel")


def test_a_service_sms_that_raises_is_logged_and_never_raises(
    db: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def broken_send(*_: Any, **__: Any) -> None:
        raise RuntimeError("smsmode down")

    monkeypatch.setattr(delivery_module.sms_service, "send_service_message", broken_send)
    assistant = _assistant(db)

    with caplog.at_level(logging.WARNING, logger=delivery_module.__name__):
        outcome = asyncio.run(
            AiAssistantMessageDelivery.send_service_sms(
                db,
                assistant,
                SmsConfig(user_id=7, sender="Dibodev"),
                to_e164="+33612345678",
                text="Test",
                recipient_name="Toitures Morel (alertes)",
                log_label=f"Alert SMS to assistant {assistant.id} owner",
            )
        )

    assert outcome is None
    assert f"Alert SMS to assistant {assistant.id} owner failed" in caplog.messages


def test_a_warning_is_journaled_under_the_business_name(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[dict[str, Any]] = []
    monkeypatch.setattr(delivery_module.activity_log_service, "record", lambda **kwargs: logged.append(kwargs))
    assistant = _assistant(db)

    AiAssistantMessageDelivery.record_warning(
        assistant, action="assistant_alert_sms_skipped", title="SMS d'alerte non envoyé", detail="Numéro désinscrit"
    )

    assert logged == [
        {
            "category": "assistant",
            "action": "assistant_alert_sms_skipped",
            "status": "warning",
            "title": "Toitures Morel · SMS d'alerte non envoyé",
            "detail": "Numéro désinscrit",
            "user_id": 7,
            "entity_type": "prospect",
            "entity_id": assistant.prospect_id,
        }
    ]
