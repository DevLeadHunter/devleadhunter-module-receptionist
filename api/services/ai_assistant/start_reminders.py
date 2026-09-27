"""
The « Pour démarrer » reminders: three days and two weeks after the sale, the business gets one email listing what
still keeps its receptionist from being found (no alert mobile, no address on its Google profile nor line on its
site, no agenda), with the way to its space. Nothing when every step is done; never more than these two.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from services.ai_assistant.business_mailer import AiAssistantBusinessMailer
from services.ai_assistant.calendar_service import ai_assistant_calendar_service
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.client_space_email import AiAssistantClientSpaceEmail

logger = logging.getLogger(__name__)

# The reminders: days after the sale, and the column that says the reminder went (or had nothing to say).
REMINDERS: tuple[tuple[int, str], ...] = ((3, "start_reminder_j3_sent_at"), (14, "start_reminder_j14_sent_at"))
# The agenda states that count as a missing step (an agenda Google cannot offer is not the client's fault).
_AGENDA_MISSING_STATES: frozenset[str] = frozenset({"disconnected", "error"})


class AiAssistantStartReminders:
    """Emails the steps left to start, at J+3 and J+14 after the sale."""

    @staticmethod
    def missing_steps(db: Session, assistant: AiAssistant) -> list[str]:
        """
        What keeps the receptionist from serving: the « Pour démarrer » steps not done yet.

        Args:
            db: Active database session.
            assistant: A sold assistant.

        Returns:
            The steps, as the client reads them; empty when everything is in place.
        """
        steps: list[str] = []
        if not assistant.alert_phone_e164:
            steps.append("votre numéro de mobile, pour recevoir les demandes par SMS")
        if assistant.installed_at is None and assistant.google_profile_linked_at is None:
            steps.append(
                f"l'adresse de {assistant.assistant_name} sur votre fiche Google, ou la ligne à coller sur votre site"
            )
        state, _calendar = ai_assistant_calendar_service.connection(db, assistant)
        if str(getattr(state, "value", state)) in _AGENDA_MISSING_STATES:
            steps.append("votre agenda Google, pour que les rendez-vous s'y posent tout seuls")
        return steps

    async def send_due(self, db: Session, *, now: datetime | None = None) -> int:
        """
        Send the reminders due: each one once, claimed before it is written so a failure never repeats hourly.

        Args:
            db: Active database session.
            now: Current time (tests); defaults to now.

        Returns:
            How many emails went.
        """
        current = (now or datetime.now(UTC)).replace(tzinfo=None)
        sold = (
            db.query(AiAssistant)
            .filter(
                AiAssistant.status == AiAssistantStatus.DELIVERED.value,
                AiAssistant.deleted_at.is_(None),
                AiAssistant.delivered_at.isnot(None),
            )
            .all()
        )
        sent = 0
        for assistant in sold:
            for days, column in REMINDERS:
                if getattr(assistant, column) is not None or assistant.delivered_at + timedelta(days=days) > current:
                    continue
                setattr(assistant, column, current)
                db.commit()
                missing = self.missing_steps(db, assistant)
                if not missing:
                    continue
                rendered = AiAssistantClientSpaceEmail.render_start_reminder(
                    business_name=assistant.business_name,
                    assistant_name=assistant.assistant_name,
                    url=AiAssistantClientLinks.url(assistant.id, now=now),
                    days=days,
                    missing=missing,
                )
                recipient = AiAssistantBusinessMailer.business_email(db, assistant)
                if not recipient:
                    logger.warning("Start reminder J+%s of assistant %s: no business email", days, assistant.id)
                    continue
                failure = await AiAssistantBusinessMailer.send(
                    db, assistant, rendered, recipient=recipient, recipient_name=assistant.business_name
                )
                if failure:
                    logger.warning("Start reminder J+%s of assistant %s not sent: %s", days, assistant.id, failure)
                    continue
                sent += 1
        return sent


ai_assistant_start_reminders = AiAssistantStartReminders()
