"""
The example client space a prospect can open from its demo page (« Voir un exemple d'espace »).

A demo assistant has no client space (it only exists once sold), and an empty space would sell nothing: this one is
a fictional business with a full month of activity, served under the reserved token « exemple », read-only. Its
dates follow the calendar so it never looks stale.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from core.config import settings
from enums.ai_assistant_calendar_status import AiAssistantCalendarConnection
from enums.ai_assistant_request import AiAssistantRequestOutcome, AiAssistantRequestStatus, AiAssistantRequestType
from enums.ai_assistant_subscription_status import AiAssistantSubscriptionStatus
from enums.ai_assistant_widget_language import AiAssistantWidgetLanguage
from schemas.ai_assistant_client_space import (
    AiAssistantClientActivityDay,
    AiAssistantClientAppointmentItem,
    AiAssistantClientCalendar,
    AiAssistantClientGoogleProfile,
    AiAssistantClientLanguageOption,
    AiAssistantClientLimit,
    AiAssistantClientRecentFigures,
    AiAssistantClientReport,
    AiAssistantClientRequestItem,
    AiAssistantClientSettings,
    AiAssistantClientSpaceResponse,
    AiAssistantClientSubscription,
)
from schemas.ai_assistant_faq import AiAssistantFaqEntry, AiAssistantUnansweredEntry
from services.ai_assistant.calendar_settings import DURATION_CHOICES, MIN_NOTICE_CHOICES
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.client_space_activity import ACTIVITY_DAYS
from services.ai_assistant.client_space_service import AiAssistantClientSpaceService
from services.ai_assistant.embed_snippet import AiAssistantEmbedSnippet
from services.ai_assistant.knowledge_builder import LANGUAGE_NAMES
from services.ai_assistant.limits import AiAssistantLimits
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.french_date_formatter import FrenchDateFormatter

# The token of the example space: never a real link (a real token is « <id>.<expiry>.<signature> »).
EXAMPLE_TOKEN = "exemple"

_BUSINESS_NAME = "Toitures Morel"
_ASSISTANT_NAME = "Sofia"
_ACCENT_COLOR = "#b45309"
# The last 30 days, oldest first, the listed requests on their days (yesterday's two, three days ago…).
_ACTIVITY_CONVERSATIONS = (1, 2, 0, 3, 1, 1, 0, 2, 4, 1, 0, 1, 2, 3, 1, 0, 2, 1, 3, 2, 1, 2, 2, 4, 2, 1, 3, 1, 4, 2)
_ACTIVITY_REQUESTS = (0, 1, 0, 1, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 0, 2, 0)


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
        five_days_ago = current - timedelta(days=5)
        eight_days_ago = current - timedelta(days=8)
        eleven_days_ago = current - timedelta(days=11)
        last_month = current.replace(day=1) - timedelta(days=1)
        next_visit = AiAssistantClientSpaceExample._next_weekday(current.date(), 3)
        return AiAssistantClientSpaceResponse(
            business_name=_BUSINESS_NAME,
            assistant_name=_ASSISTANT_NAME,
            accent_color=_ACCENT_COLOR,
            link_expires_label=f"{current + timedelta(days=AiAssistantClientLinks.TTL_DAYS):%d/%m/%Y}",
            is_example=True,
            fresh_token=None,
            website_url=None,
            embed_snippet=AiAssistantEmbedSnippet.render("toitures-morel"),
            google_profile=AiAssistantClientSpaceExample._google_profile(),
            installed=None,
            limits=[
                AiAssistantClientLimit(key=limit.key, topic=limit.topic, answer=limit.answer, enabled=limit.enabled)
                for limit in AiAssistantLimits.defaults(_BUSINESS_NAME)
            ],
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
                    received_day=f"{yesterday:%Y-%m-%d}",
                    received_time="21:43",
                    received_outside_hours=True,
                    photo_urls=[f"{settings.demo_host_base_url.rstrip('/')}/showroom/examples/toiture.jpg"],
                ),
                AiAssistantClientRequestItem(
                    id=2,
                    type=AiAssistantRequestType.APPOINTMENT,
                    status=AiAssistantRequestStatus.NEW,
                    name="Julien Bernard",
                    contact="julien.bernard@exemple.fr",
                    summary="Devis pour l'isolation des combles, environ 60 m².",
                    received_label=f"{yesterday:%d/%m} à 12:10",
                    received_day=f"{yesterday:%Y-%m-%d}",
                    received_time="12:10",
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
                    received_day=f"{earlier:%Y-%m-%d}",
                    received_time="08:05",
                    received_outside_hours=False,
                    outcome=AiAssistantRequestOutcome.WON,
                ),
                AiAssistantClientRequestItem(
                    id=4,
                    type=AiAssistantRequestType.QUOTE,
                    status=AiAssistantRequestStatus.HANDLED,
                    name="Marc Dubois",
                    contact="06 23 45 67 89",
                    summary="Réfection complète d'une toiture de 90 m² en tuiles mécaniques.",
                    received_label=f"{five_days_ago:%d/%m} à 19:12",
                    received_day=f"{five_days_ago:%Y-%m-%d}",
                    received_time="19:12",
                    received_outside_hours=True,
                    outcome=AiAssistantRequestOutcome.WON,
                ),
                AiAssistantClientRequestItem(
                    id=5,
                    type=AiAssistantRequestType.APPOINTMENT,
                    status=AiAssistantRequestStatus.HANDLED,
                    name="Emma Laurent",
                    contact="06 34 56 78 90",
                    summary="Un velux fuit dans la chambre, souhaite une visite un samedi matin.",
                    received_label=f"{eight_days_ago:%d/%m} à 07:48",
                    received_day=f"{eight_days_ago:%Y-%m-%d}",
                    received_time="07:48",
                    received_outside_hours=True,
                ),
                AiAssistantClientRequestItem(
                    id=6,
                    type=AiAssistantRequestType.QUOTE,
                    status=AiAssistantRequestStatus.HANDLED,
                    name="Thomas Garnier",
                    contact="thomas.garnier@exemple.fr",
                    summary="Nettoyage et démoussage du toit d'une longère avant la vente.",
                    received_label=f"{eleven_days_ago:%d/%m} à 10:30",
                    received_day=f"{eleven_days_ago:%Y-%m-%d}",
                    received_time="10:30",
                    received_outside_hours=False,
                    outcome=AiAssistantRequestOutcome.LOST,
                ),
            ],
            recent=AiAssistantClientRecentFigures(
                days=ACTIVITY_DAYS,
                conversations=sum(_ACTIVITY_CONVERSATIONS),
                requests=sum(_ACTIVITY_REQUESTS),
                quotes=7,
                won=4,
                outside_hours_pct=58,
            ),
            activity=[
                AiAssistantClientActivityDay(
                    day=f"{current.date() - timedelta(days=ACTIVITY_DAYS - 1 - offset):%Y-%m-%d}",
                    conversations=conversations,
                    requests=requests,
                )
                for offset, (conversations, requests) in enumerate(
                    zip(_ACTIVITY_CONVERSATIONS, _ACTIVITY_REQUESTS, strict=True)
                )
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
                won=4,
                won_line=f"{_ASSISTANT_NAME} vous a apporté 4 clients ce mois-ci.",
                top_questions=[
                    "Intervenez-vous sur les toits en ardoise ?",
                    "Faites-vous le démoussage ?",
                    "Quel délai pour un devis ?",
                ],
            ),
            settings=AiAssistantClientSettings(
                assistant_name=_ASSISTANT_NAME,
                languages=[AiAssistantWidgetLanguage.FR, AiAssistantWidgetLanguage.EN],
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
                for language in AiAssistantWidgetLanguage
            ],
            subscription=AiAssistantClientSubscription(
                status=AiAssistantSubscriptionStatus.ACTIVE,
                price_label="79 €/mois",
                period_end_label=f"{current + timedelta(days=19):%d/%m/%Y}",
                cancel_scheduled=False,
                can_manage=True,
            ),
            calendar=AiAssistantClientCalendar(
                status=AiAssistantCalendarConnection.CONNECTED,
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
    def _google_profile() -> AiAssistantClientGoogleProfile:
        """The fictional receptionist's address, so the « fiche Google » screen reads like the real one."""
        url = f"{settings.demo_host_base_url.rstrip('/')}/ia/toitures-morel"
        short_link = url.split("://", 1)[-1]
        return AiAssistantClientGoogleProfile(
            page_url=url,
            short_link=short_link,
            qr_svg=AiAssistantClientSpaceService.qr_svg(url),
            voicemail_text=(
                f"Bonjour, vous êtes bien chez {_BUSINESS_NAME}. Je ne peux pas vous répondre pour le moment. "
                f"Écrivez à {_ASSISTANT_NAME}, ma réceptionniste, sur {short_link} : votre demande est notée, avec une "
                "photo si besoin, et je vous rappelle dès que possible. À bientôt."
            ),
            linked_at_label=None,
            is_linked=False,
        )

    @staticmethod
    def _next_weekday(day: date, days_ahead: int) -> date:
        """The date ``days_ahead`` days later, pushed past the weekend (an appointment is never on a Sunday)."""
        candidate = day + timedelta(days=days_ahead)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate


ai_assistant_client_space_example = AiAssistantClientSpaceExample()
