"""
What the assistant's outgoing messages share: sent once, texted through the operator's sender, warnings journaled.

A one-shot message (an alert, a reminder, a report's send attempt) is claimed on its row before it leaves: one
conditional update, so two passes never both send it. A service SMS goes through the operator's SMS sender and
never raises. What the operator should know (a message that did not leave, a setting a client changed) is written
to their activity log, under the business's name.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute, Session

from models.ai_assistant import AiAssistant
from models.ai_assistant_appointment import AiAssistantAppointment
from models.ai_assistant_report import AiAssistantReport
from models.ai_assistant_request import AiAssistantRequest
from models.sms_config import SmsConfig
from services.activity_log_service import CATEGORY_ASSISTANT, STATUS_WARNING, activity_log_service
from services.sms_service import SmsSendOutcome, sms_service

logger = logging.getLogger(__name__)


class AiAssistantMessageDelivery:
    """Claims a one-shot message on its row, texts through the operator's SMS sender, journals the warnings."""

    @staticmethod
    def claim(
        db: Session,
        row: AiAssistantRequest | AiAssistantAppointment | AiAssistantReport,
        *conditions: ColumnElement[bool],
        values: Mapping[InstrumentedAttribute[Any], object],
    ) -> bool:
        """
        Update a row only while the conditions still hold, in one statement, so two passes never both act on it.

        Args:
            db: Active database session (committed).
            row: The row the message is claimed on (refreshed).
            conditions: What must still hold (a stamp still empty, a request still new, an attempt count unchanged).
            values: What the update writes (the stamp, the attempt count…).

        Returns:
            True when this call updated the row, False when a condition no longer held.
        """
        model = type(row)
        claimed = db.query(model).filter(model.id == row.id, *conditions).update(values, synchronize_session=False)
        db.commit()
        db.refresh(row)
        return claimed == 1

    @staticmethod
    async def send_service_sms(
        db: Session,
        assistant: AiAssistant,
        config: SmsConfig,
        *,
        to_e164: str,
        text: str,
        recipient_name: str,
        log_label: str,
    ) -> SmsSendOutcome | None:
        """
        Text someone for the assistant's business through the operator's SMS sender, as a service message.

        Args:
            db: Active database session (rolled back when the send raises).
            assistant: The assistant the SMS is about.
            config: The operator's SMS configuration.
            to_e164: The recipient's mobile.
            text: The text, one GSM-7 segment.
            recipient_name: The recipient's label in the SMS log.
            log_label: How the server log names this SMS when the send raises (« Appointment 12 SMS »).

        Returns:
            The SMS service's outcome, or None when the send raised.
        """
        try:
            return await sms_service.send_service_message(
                db,
                user_id=assistant.user_id,
                config=config,
                to_e164=to_e164,
                text=text,
                recipient_name=recipient_name,
            )
        except Exception:
            logger.warning("%s failed", log_label, exc_info=True)
            db.rollback()
            return None

    @staticmethod
    def record_warning(assistant: AiAssistant, *, action: str, title: str, detail: str) -> None:
        """
        Write a warning about an assistant's business in the operator's activity log.

        Args:
            assistant: The assistant.
            action: The log action (« assistant_alert_sms_skipped »).
            title: What happened, shown after the business name (« SMS d'alerte non envoyé »).
            detail: Why, or what changed.
        """
        activity_log_service.record(
            category=CATEGORY_ASSISTANT,
            action=action,
            status=STATUS_WARNING,
            title=f"{assistant.business_name} · {title}",
            detail=detail,
            user_id=assistant.user_id,
            entity_type="prospect" if assistant.prospect_id else None,
            entity_id=assistant.prospect_id,
        )
