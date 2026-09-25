"""
The example client space a prospect can open from its demo page (« Voir un exemple d'espace »).

A demo assistant has no client space (it only exists once sold), and an empty space would sell nothing: this one is
a fictional business with a full month of activity, served under the reserved token « exemple », read-only. Its
dates follow the calendar so it never looks stale.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from enums.ai_assistant_request import AiAssistantRequestStatus, AiAssistantRequestType
from enums.assistant_calendar_status import AssistantCalendarConnection
from enums.assistant_subscription_status import AssistantSubscriptionStatus
from enums.assistant_widget_language import AssistantWidgetLanguage
from schemas.ai_assistant_client_space import (
    AiAssistantClientAppointmentItem,
    AiAssistantClientCalendar,
    AiAssistantClientLanguageOption,
    AiAssistantClientReport,
    AiAssistantClientRequestItem,
    AiAssistantClientSettings,
    AiAssistantClientSpaceResponse,
    AiAssistantClientSubscription,
)
from schemas.ai_assistant_faq import AiAssistantFaqEntry, AiAssistantUnansweredEntry
from services.ai_assistant.calendar_settings import DURATION_CHOICES, MIN_NOTICE_CHOICES
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.knowledge_builder import LANGUAGE_NAMES
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.french_date_formatter import FrenchDateFormatter

# The token of the example space: never a real link (a real token is « <id>.<expiry>.<signature> »).
EXAMPLE_TOKEN = "exemple"

_BUSINESS_NAME = "Toitures Morel"
_ASSISTANT_NAME = "Sofia"
_ACCENT_COLOR = "#b45309"


class AiAssistantClientSpaceExample:
    """Builds the example space, dated from now."""

    @staticmethod
    def build(*, now: datetime | None = None) -> AiAssistantClientSpaceResponse:
        """
        The example space as the page reads it.

        Args:
            now: Current time (tests); defaults to now, in the business's time.

        Returns:
            A read-only space (``is_example``) with requests, a report, answers, settings and an agenda.
        """
        current = now or OpeningHoursCalendar.business_now()
        yesterday = current - timedelta(days=1)
        earlier = current - timedelta(days=3)
        last_month = current.replace(day=1) - timedelta(days=1)
        next_visit = AiAssistantClientSpaceExample._next_weekday(current.date(), 3)
        return AiAssistantClientSpaceResponse(
            business_name=_BUSINESS_NAME,
            assistant_name=_ASSISTANT_NAME,
            accent_color=_ACCENT_COLOR,
            link_expires_label=f"{current + timedelta(days=AiAssistantClientLinks.TTL_DAYS):%d/%m/%Y}",
            is_example=True,
            pending_count=2,
            requests=[
                AiAssistantClientRequestItem(
                    id=1,
                    type=AiAssistantRequestType.URGENT,
                    status=AiAssistantRequestStatus.NEW,
                    name="Claire Martin",
                    contact="06 12 34 56 78",
                    summary="Fuite depuis la tempête, des tuiles ont bougé côté rue. Souhaite un passage cette semaine.",
                    received_label=f"{yesterday:%d/%m} à 21:43",
                    received_outside_hours=True,
                ),
                AiAssistantClientRequestItem(
                    id=2,
                    type=AiAssistantRequestType.APPOINTMENT,
                    status=AiAssistantRequestStatus.NEW,
                    name="Julien Bernard",
                    contact="julien.bernard@exemple.fr",
                    summary="Devis pour l'isolation des combles, environ 60 m².",
                    received_label=f"{yesterday:%d/%m} à 12:10",
                    received_outside_hours=False,
                    appointment_slots=[
                        f"{FrenchDateFormatter.short_date(next_visit)}, matin",
                        f"{FrenchDateFormatter.short_date(next_visit + timedelta(days=1))}, après-midi",
                    ],
                ),
                AiAssistantClientRequestItem(
                    id=3,
                    type=AiAssistantRequestType.QUOTE,
                    status=AiAssistantRequestStatus.HANDLED,
                    name="Sophie Leroy",
                    contact="06 98 76 54 32",
                    summary="Remplacement des gouttières d'une maison de plain-pied.",
                    received_label=f"{earlier:%d/%m} à 08:05",
                    received_outside_hours=False,
                ),
            ],
            report=AiAssistantClientReport(
                month_label=FrenchDateFormatter.month_year(last_month),
                conversations=41,
                requests=14,
                quotes=6,
                appointments=4,
                urgent=1,
                photo_requests=5,
                outside_hours_pct=58,
                languages_line="français 90 %, anglais 10 %",
                handling_line="12 demandes marquées traitées, en 3 h en moyenne.",
                top_questions=[
                    "Intervenez-vous sur les toits en ardoise ?",
                    "Faites-vous le démoussage ?",
                    "Quel délai pour un devis ?",
                ],
            ),
            settings=AiAssistantClientSettings(
                assistant_name=_ASSISTANT_NAME,
                languages=[AssistantWidgetLanguage.FR, AssistantWidgetLanguage.EN],
                alert_phone="+33612345678",
                alert_sms_enabled=True,
                alert_email_enabled=True,
                alert_sms_types=[
                    AiAssistantRequestType.QUOTE,
                    AiAssistantRequestType.APPOINTMENT,
                    AiAssistantRequestType.URGENT,
                ],
                alert_quiet_start_hour=22,
                alert_quiet_end_hour=8,
            ),
            language_options=[
                AiAssistantClientLanguageOption(code=language, label=LANGUAGE_NAMES.get(language.value, language.value))
                for language in AssistantWidgetLanguage
            ],
            subscription=AiAssistantClientSubscription(
                status=AssistantSubscriptionStatus.ACTIVE,
                price_label="79 €/mois",
                period_end_label=f"{current + timedelta(days=19):%d/%m/%Y}",
                cancel_scheduled=False,
                can_manage=True,
            ),
            calendar=AiAssistantClientCalendar(
                status=AssistantCalendarConnection.CONNECTED,
                account_email="contact@toitures-morel.fr",
                calendar_id="primary",
                duration_minutes=60,
                min_notice_hours=24,
                appointment_types=["Visite technique", "Devis sur place"],
                duration_choices=list(DURATION_CHOICES),
                min_notice_choices=list(MIN_NOTICE_CHOICES),
            ),
            appointments=[
                AiAssistantClientAppointmentItem(
                    id=1,
                    start_label=f"{FrenchDateFormatter.short_date(next_visit + timedelta(days=2))} à 09:00",
                    type_label="Devis sur place",
                    name="Nadia Petit",
                    contact="06 45 67 89 01",
                )
            ],
            faq=[
                AiAssistantFaqEntry(
                    question="Intervenez-vous sur les toits en ardoise ?",
                    answer="Oui, ardoise et tuile, sur tout le bassin rennais.",
                    created_at=earlier,
                ),
                AiAssistantFaqEntry(
                    question="Faites-vous le démoussage ?",
                    answer="Oui, avec un traitement hydrofuge. Le devis se fait sur place.",
                    created_at=earlier,
                ),
            ],
            unanswered=[
                AiAssistantUnansweredEntry(
                    question="Proposez-vous un paiement en plusieurs fois ?",
                    count=3,
                    first_seen=earlier,
                    last_seen=yesterday,
                )
            ],
        )

    @staticmethod
    def _next_weekday(day: date, days_ahead: int) -> date:
        """The date ``days_ahead`` days later, pushed past the weekend (an appointment is never on a Sunday)."""
        candidate = day + timedelta(days=days_ahead)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate


ai_assistant_client_space_example = AiAssistantClientSpaceExample()
