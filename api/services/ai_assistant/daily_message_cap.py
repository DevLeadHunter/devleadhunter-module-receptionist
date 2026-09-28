"""
The daily cap on the visitor messages an assistant answers with the model.

Past the cap, the chat answers a fixed sentence without calling the model until the end of the business day
(midnight, Paris time: every targeted country keeps it) and the widget offers its contact form. The count is read
from the conversation journal, so it holds across the API workers and their restarts. The operator's test visits
(« ?internal=1 ») are counted apart: they never use the business's budget, and a spoofed test flag still stops at
the same cap. The operator who owns the assistant is told once a day, never the business.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time
from typing import ClassVar

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.config import settings
from enums.assistant_widget_language import AssistantWidgetLanguage
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.ai_assistant_message import AiAssistantMessage
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.notification_service import notification_service

logger = logging.getLogger(__name__)

# The spaced hyphen or dash before the descriptive part of a Maps listing (« Toitures Morel - Couvreur Rennes »).
_LISTING_DESCRIPTION_SEPARATOR = re.compile(r"\s+[-–—]\s+")


class AiAssistantDailyMessageCap:
    """Counts an assistant's visitor messages of the day, words the capped reply and alerts the operator once."""

    CAPPED_REPLIES: ClassVar[dict[AssistantWidgetLanguage, str]] = {
        AssistantWidgetLanguage.FR: "{name} ne peut plus répondre aujourd'hui : laissez votre numéro, {business} vous rappelle.",
        AssistantWidgetLanguage.NL: "{name} kan vandaag niet meer antwoorden: laat uw nummer achter, {business} belt u terug.",
        AssistantWidgetLanguage.EN: "{name} can't answer any more today: leave your number and {business} will call you back.",
        AssistantWidgetLanguage.DE: (
            "{name} kann heute nicht mehr antworten: Hinterlassen Sie Ihre Nummer, {business} ruft Sie zurück."
        ),
        AssistantWidgetLanguage.LB: "{name} kann haut net méi äntweren: loosst Är Nummer do, {business} rifft Iech zréck.",
    }

    @staticmethod
    def cap() -> int:
        """The visitor messages a business day an assistant answers with the model."""
        return settings.assistant_daily_visitor_message_cap

    @staticmethod
    def day_start(local_now: datetime) -> datetime:
        """
        The start of the business day of a moment, as the database stores times.

        Args:
            local_now: An aware moment in the business time zone.

        Returns:
            Midnight of that day in Paris, naive UTC.
        """
        midnight = datetime.combine(local_now.date(), time.min, tzinfo=OpeningHoursCalendar.business_timezone())
        return OpeningHoursCalendar.to_utc(midnight)

    def visitor_messages_today(
        self, db: Session, assistant_id: int, *, is_test: bool, local_now: datetime | None = None
    ) -> int:
        """
        How many messages visitors sent an assistant since midnight (business time).

        Args:
            db: Active database session.
            assistant_id: The assistant.
            is_test: Count the operator's test visits instead of the business's visitors.
            local_now: The business's current time (tests); defaults to now.

        Returns:
            The count of today's visitor messages of that kind.
        """
        since = self.day_start(local_now or OpeningHoursCalendar.business_now())
        kind = AiAssistantConversation.is_test.is_(True) if is_test else AiAssistantConversation.is_test.is_not(True)
        count: int | None = (
            db.query(func.count(AiAssistantMessage.id))
            .join(AiAssistantConversation, AiAssistantMessage.conversation_id == AiAssistantConversation.id)
            .filter(
                AiAssistantConversation.assistant_id == assistant_id,
                # Only a conversation active today can hold a message of today: it keeps the scan to today's.
                AiAssistantConversation.last_message_at >= since,
                kind,
                AiAssistantMessage.role == "user",
                AiAssistantMessage.created_at >= since,
            )
            .scalar()
        )
        return count or 0

    def is_reached(
        self, db: Session, assistant: AiAssistant, *, is_test: bool, local_now: datetime | None = None
    ) -> bool:
        """
        Whether an assistant already answered today's cap of visitor messages.

        Args:
            db: Active database session.
            assistant: The assistant.
            is_test: The message comes from the operator's test visit (``?internal=1``).
            local_now: The business's current time (tests); defaults to now.

        Returns:
            True once today's messages of that kind reach the cap.
        """
        return self.visitor_messages_today(db, assistant.id, is_test=is_test, local_now=local_now) >= self.cap()

    @classmethod
    def capped_reply(cls, assistant: AiAssistant, language: str | None) -> str:
        """
        The sentence a visitor reads once the cap is reached, in the widget's language (French by default).

        Args:
            assistant: The assistant (its persona's first name and the business).
            language: The widget language.

        Returns:
            The fixed reply, asking for a number to call back.
        """
        widget_language = AssistantWidgetLanguage.from_code(language) or AssistantWidgetLanguage.FR
        business = _LISTING_DESCRIPTION_SEPARATOR.split(assistant.business_name)[0].strip() or assistant.business_name
        return cls.CAPPED_REPLIES[widget_language].format(name=assistant.assistant_name, business=business)

    async def alert_operator_once(
        self, db: Session, assistant: AiAssistant, *, local_now: datetime | None = None
    ) -> bool:
        """
        Tell the operator who owns the assistant that its cap is reached, at most once a business day.

        The day is claimed on the assistant's row first, so concurrent requests and workers alert once. Never
        raises: a failed notification must not cost the visitor their reply.

        Args:
            db: Active database session (committed).
            assistant: The capped assistant.
            local_now: The business's current time (tests); defaults to now.

        Returns:
            True when this call sent today's alert.
        """
        today: date = (local_now or OpeningHoursCalendar.business_now()).date()
        try:
            claimed = (
                db.query(AiAssistant)
                .filter(
                    AiAssistant.id == assistant.id,
                    or_(AiAssistant.message_cap_alerted_on.is_(None), AiAssistant.message_cap_alerted_on != today),
                )
                .update({AiAssistant.message_cap_alerted_on: today}, synchronize_session=False)
            )
            db.commit()
            if not claimed:
                return False
            await notification_service.notify_assistant_daily_cap_reached(
                db,
                user_id=assistant.user_id,
                prospect_id=assistant.prospect_id,
                fallback_name=assistant.business_name,
                cap=self.cap(),
            )
            return True
        except Exception as exc:
            logger.warning("Assistant %s daily cap alert failed (%s)", assistant.id, type(exc).__name__)
            db.rollback()
            return False


ai_assistant_daily_message_cap = AiAssistantDailyMessageCap()
