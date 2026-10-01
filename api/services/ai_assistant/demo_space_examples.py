"""
The examples a demo space shows for the business's trade: fictional requests while the visitor has left fewer than two
of their own, and the figures of an example monthly report (a demo has no report).

The trade is the one the demo page's estimate reads from the Google category (``request_volume``): couvreur,
charpentier, carrosserie (garages included, like the demo page's example), restaurant and food truck, plombier, and a
set for every other trade. Names are fictional, phone numbers come from the range ARCEP keeps for fiction
(06 39 98 xx xx) and addresses from ``example.com``: an example never reaches anyone and never passes for a real
request (negative ids, ``is_example``). The receptionist's lines state no fact about the business and give no price.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Literal

from core.config import settings
from enums.ai_assistant_request import (
    AiAssistantRequestOutcome,
    AiAssistantRequestStatus,
    AiAssistantRequestType,
)
from enums.ai_assistant_trade import AiAssistantTrade
from models.ai_assistant import AiAssistant
from schemas.ai_assistant import AiAssistantTranscriptLine
from schemas.ai_assistant_demo_space import AiAssistantDemoSpaceReport, AiAssistantDemoSpaceRequestItem
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots, AppointmentDay, AppointmentSlot
from services.ai_assistant.client_space_payload import ai_assistant_client_space_payload
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.photo_service import PHOTO_JOURNAL_MARKER
from services.ai_assistant.report_email import LanguageShare, MonthlyStats
from services.ai_assistant.trade_resolver import AiAssistantTradeResolver
from services.french_date_formatter import FrenchDateFormatter


@dataclass(frozen=True)
class ExampleTurn:
    """One turn of an example conversation; « {business} » and « {event_day} » are filled in when it is shown."""

    role: Literal["user", "assistant"]
    text: str
    # The turn is the visitor's photo: the example's own photo, journaled like a real photo turn.
    is_photo: bool = False


@dataclass(frozen=True)
class ExampleEvent:
    """The event an example request describes: a Saturday so many weeks ahead, its guests and its budget."""

    weeks_ahead: int
    guests: int
    budget: str


@dataclass(frozen=True)
class ExampleRequest:
    """A fictional request of a trade, with a fictional name and contact."""

    type: AiAssistantRequestType
    status: AiAssistantRequestStatus
    name: str
    contact: str
    summary: str
    # When it came in, in business time: so many days before today, at this hour.
    days_ago: int
    received_at: time
    turns: tuple[ExampleTurn, ...]
    # A file of the demo host's ``/showroom/examples/``, without its extension: the photo the visitor sent.
    photo: str | None = None
    # How many of the business's next open half-days the visitor wished for an appointment.
    wished_half_days: int = 0
    outcome: AiAssistantRequestOutcome | None = None
    event: ExampleEvent | None = None


@dataclass(frozen=True)
class TradeExamples:
    """The examples of a trade: its requests, the ones to show first first, and its example month."""

    requests: tuple[ExampleRequest, ...]
    # The example month; its languages follow the receptionist's, filled in when it is shown.
    report: MonthlyStats


_PHOTO_TURN = ExampleTurn(role="user", text=PHOTO_JOURNAL_MARKER, is_photo=True)

_ROOFER = TradeExamples(
    requests=(
        ExampleRequest(
            type=AiAssistantRequestType.URGENT,
            status=AiAssistantRequestStatus.NEW,
            name="Claire Martin",
            contact="06 39 98 12 34",
            summary="Fuite depuis la tempête, des tuiles ont bougé côté rue. Souhaite un passage cette semaine.",
            days_ago=1,
            received_at=time(21, 43),
            photo="toiture",
            turns=(
                ExampleTurn(
                    "user",
                    "Bonsoir, j'ai une fuite depuis la tempête, des tuiles ont bougé côté rue. "
                    "Vous pouvez passer cette semaine ?",
                ),
                ExampleTurn(
                    "assistant", "Je transmets en urgence à {business}. Pouvez-vous m'envoyer une photo du toit ?"
                ),
                _PHOTO_TURN,
                ExampleTurn(
                    "assistant",
                    "Merci, la photo est jointe à votre demande. Votre prénom et un téléphone, pour que {business} "
                    "vous rappelle ?",
                ),
                ExampleTurn("user", "Claire Martin, 06 39 98 12 34"),
                ExampleTurn(
                    "assistant", "C'est transmis en urgence, Claire. {business} vous rappelle dès que possible."
                ),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.QUOTE,
            status=AiAssistantRequestStatus.HANDLED,
            name="Sophie Leroy",
            contact="06 39 98 45 67",
            summary="Remplacement des gouttières d'une maison de plain-pied.",
            days_ago=4,
            received_at=time(8, 5),
            outcome=AiAssistantRequestOutcome.WON,
            turns=(
                ExampleTurn(
                    "user",
                    "Bonjour, nos gouttières sont à changer, c'est une maison de plain-pied. "
                    "Vous pouvez faire un devis ?",
                ),
                ExampleTurn("assistant", "Avec plaisir. {business} vous rappelle pour en parler. À quel numéro ?"),
                ExampleTurn("user", "06 39 98 45 67, Sophie Leroy"),
                ExampleTurn("assistant", "Merci Sophie, c'est transmis à {business}."),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.APPOINTMENT,
            status=AiAssistantRequestStatus.NEW,
            name="Julien Bernard",
            contact="julien.bernard@example.com",
            summary="Isolation des combles, environ 60 m². Souhaite une visite pour un devis.",
            days_ago=1,
            received_at=time(12, 10),
            wished_half_days=2,
            turns=(
                ExampleTurn(
                    "user",
                    "Bonjour, je voudrais faire isoler mes combles, environ 60 m². Quelqu'un peut passer voir ?",
                ),
                ExampleTurn(
                    "assistant",
                    "Avec plaisir. Je note les demi-journées qui vous arrangent et votre e-mail : {business} vous "
                    "confirme l'heure de la visite.",
                ),
            ),
        ),
    ),
    report=MonthlyStats(
        conversations=41,
        requests=14,
        quotes=6,
        appointments=4,
        urgent=1,
        photo_requests=5,
        handled=12,
        outside_hours_pct=58,
        languages=(),
        average_handling_hours=3.0,
        top_questions=(
            "Intervenez-vous sur les toits en ardoise ?",
            "Faites-vous le démoussage ?",
            "Quel délai pour un devis ?",
        ),
        won=4,
    ),
)

_CARPENTER = TradeExamples(
    requests=(
        ExampleRequest(
            type=AiAssistantRequestType.QUOTE,
            status=AiAssistantRequestStatus.NEW,
            name="Thomas Girard",
            contact="06 39 98 23 45",
            summary="Lucarne du grenier abîmée : le bois du cadre a pourri et l'eau commence à entrer.",
            days_ago=1,
            received_at=time(20, 52),
            photo="toiture",
            turns=(
                ExampleTurn(
                    "user",
                    "Bonsoir, la lucarne de mon grenier est abîmée : le bois du cadre a pourri et l'eau commence à "
                    "entrer. Vous pouvez venir voir ?",
                ),
                ExampleTurn("assistant", "Je transmets à {business}. Pouvez-vous m'envoyer une photo de la lucarne ?"),
                _PHOTO_TURN,
                ExampleTurn(
                    "assistant",
                    "Merci, la photo est jointe à votre demande. Votre prénom et un téléphone, pour que {business} "
                    "vous rappelle ?",
                ),
                ExampleTurn("user", "Thomas Girard, 06 39 98 23 45"),
                ExampleTurn("assistant", "Merci Thomas, c'est transmis à {business}. On vous rappelle au plus vite."),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.QUOTE,
            status=AiAssistantRequestStatus.HANDLED,
            name="Antoine Mercier",
            contact="06 39 98 56 78",
            summary="Carport en bois pour deux voitures, contre la maison.",
            days_ago=5,
            received_at=time(10, 30),
            outcome=AiAssistantRequestOutcome.WON,
            turns=(
                ExampleTurn(
                    "user",
                    "Bonjour, je cherche un carport en bois pour deux voitures, contre la maison. "
                    "Vous pouvez me faire un devis ?",
                ),
                ExampleTurn(
                    "assistant",
                    "Avec plaisir. {business} vous rappelle pour les dimensions et le terrain. À quel numéro ?",
                ),
                ExampleTurn("user", "Antoine Mercier, 06 39 98 56 78"),
                ExampleTurn("assistant", "Merci Antoine, c'est transmis à {business}."),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.QUOTE,
            status=AiAssistantRequestStatus.NEW,
            name="Camille Roux",
            contact="camille.roux@example.com",
            summary="Extension en ossature bois d'environ 20 m². Souhaite un devis.",
            days_ago=2,
            received_at=time(9, 15),
            turns=(
                ExampleTurn(
                    "user",
                    "Bonjour, nous voulons agrandir avec une extension en ossature bois d'environ 20 m². "
                    "Vous faites les devis ?",
                ),
                ExampleTurn(
                    "assistant",
                    "Avec plaisir. {business} vous recontacte pour parler du projet. Votre prénom et votre e-mail ?",
                ),
                ExampleTurn("user", "Camille Roux, camille.roux@example.com"),
                ExampleTurn("assistant", "Merci Camille, votre projet est transmis à {business}."),
            ),
        ),
    ),
    report=MonthlyStats(
        conversations=26,
        requests=9,
        quotes=6,
        appointments=2,
        urgent=0,
        photo_requests=3,
        handled=8,
        outside_hours_pct=52,
        languages=(),
        average_handling_hours=5.0,
        top_questions=(
            "Faites-vous les extensions en ossature bois ?",
            "Pouvez-vous reprendre une charpente ancienne ?",
            "Posez-vous des carports ?",
        ),
        won=2,
    ),
)

_BODYWORK = TradeExamples(
    requests=(
        ExampleRequest(
            type=AiAssistantRequestType.QUOTE,
            status=AiAssistantRequestStatus.NEW,
            name="Karim Benali",
            contact="06 39 98 67 89",
            summary="Portière arrière enfoncée après un accrochage sur un parking. Souhaite un devis.",
            days_ago=1,
            received_at=time(19, 58),
            photo="carrosserie",
            turns=(
                ExampleTurn(
                    "user",
                    "Bonsoir, on m'a enfoncé la portière arrière sur un parking. Vous pouvez me faire un devis ?",
                ),
                ExampleTurn(
                    "assistant",
                    "Avec plaisir. Pouvez-vous m'envoyer une photo de la portière ? Je la joins à votre demande pour "
                    "{business}.",
                ),
                _PHOTO_TURN,
                ExampleTurn(
                    "assistant",
                    "Merci, c'est joint. Votre prénom et un téléphone, pour que {business} vous rappelle ?",
                ),
                ExampleTurn("user", "Karim Benali, 06 39 98 67 89"),
                ExampleTurn("assistant", "Merci Karim, c'est transmis à {business}. On vous rappelle au plus vite."),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.QUOTE,
            status=AiAssistantRequestStatus.HANDLED,
            name="Hugo Lambert",
            contact="06 39 98 78 90",
            summary="Peinture du capot qui s'écaille. Demande si c'est réparable.",
            days_ago=4,
            received_at=time(9, 12),
            outcome=AiAssistantRequestOutcome.WON,
            turns=(
                ExampleTurn("user", "Bonjour, la peinture de mon capot s'écaille. C'est réparable ?"),
                ExampleTurn(
                    "assistant",
                    "{business} vous le dira en voyant la voiture. Je transmets : à quel numéro peut-on vous rappeler ?",
                ),
                ExampleTurn("user", "Hugo Lambert, 06 39 98 78 90"),
                ExampleTurn("assistant", "Merci Hugo, c'est transmis à {business}."),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.APPOINTMENT,
            status=AiAssistantRequestStatus.NEW,
            name="Élodie Fournier",
            contact="elodie.fournier@example.com",
            summary="Pare-chocs avant fissuré. Souhaite passer montrer la voiture.",
            days_ago=2,
            received_at=time(11, 24),
            wished_half_days=2,
            turns=(
                ExampleTurn(
                    "user", "Bonjour, mon pare-chocs avant est fissuré. Je peux passer vous montrer la voiture ?"
                ),
                ExampleTurn(
                    "assistant",
                    "Avec plaisir. Je note les demi-journées qui vous arrangent et votre e-mail : {business} vous "
                    "confirme l'heure.",
                ),
            ),
        ),
    ),
    report=MonthlyStats(
        conversations=52,
        requests=18,
        quotes=11,
        appointments=5,
        urgent=0,
        photo_requests=9,
        handled=16,
        outside_hours_pct=47,
        languages=(),
        average_handling_hours=2.0,
        top_questions=(
            "Travaillez-vous avec mon assurance ?",
            "Prêtez-vous un véhicule pendant les réparations ?",
            "Faites-vous le débosselage sans peinture ?",
        ),
        won=6,
    ),
)

_FOOD = TradeExamples(
    requests=(
        ExampleRequest(
            type=AiAssistantRequestType.QUOTE,
            status=AiAssistantRequestStatus.NEW,
            name="Léa Moreau",
            contact="06 39 98 89 01",
            summary="Anniversaire de 40 personnes, budget autour de 600 €. Souhaite une proposition.",
            days_ago=1,
            received_at=time(22, 15),
            event=ExampleEvent(weeks_ahead=6, guests=40, budget="600 €"),
            turns=(
                ExampleTurn(
                    "user",
                    "Bonsoir, je fête mes 40 ans le {event_day} avec 40 personnes. Vous pouvez vous occuper du repas ?",
                ),
                ExampleTurn(
                    "assistant",
                    "Avec plaisir, je note le {event_day} pour 40 personnes. {business} vérifie la date et vous fait "
                    "une proposition. Vous avez un budget en tête ?",
                ),
                ExampleTurn("user", "Autour de 600 €."),
                ExampleTurn(
                    "assistant", "C'est noté. Votre prénom et un téléphone, pour que {business} vous rappelle ?"
                ),
                ExampleTurn("user", "Léa Moreau, 06 39 98 89 01"),
                ExampleTurn("assistant", "Merci Léa, c'est transmis à {business}."),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.QUESTION,
            status=AiAssistantRequestStatus.HANDLED,
            name="Inès Garnier",
            contact="06 39 98 90 12",
            summary="Demande s'il y a des plats végétariens et sans gluten : sa fille est cœliaque.",
            days_ago=3,
            received_at=time(11, 5),
            outcome=AiAssistantRequestOutcome.WON,
            turns=(
                ExampleTurn("user", "Bonjour, vous avez des plats végétariens et sans gluten ? Ma fille est cœliaque."),
                ExampleTurn(
                    "assistant",
                    "Je pose la question à {business}, qui vous rappelle pour vous répondre. À quel numéro ?",
                ),
                ExampleTurn("user", "06 39 98 90 12, Inès Garnier"),
                ExampleTurn("assistant", "Merci Inès, c'est transmis à {business}."),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.QUOTE,
            status=AiAssistantRequestStatus.NEW,
            name="Paul Chevalier",
            contact="paul.chevalier@example.com",
            summary="12 menus à emporter pour un déjeuner d'équipe, vendredi midi.",
            days_ago=2,
            received_at=time(10, 40),
            turns=(
                ExampleTurn(
                    "user",
                    "Bonjour, on voudrait 12 menus à emporter pour un déjeuner d'équipe vendredi midi. "
                    "C'est possible ?",
                ),
                ExampleTurn(
                    "assistant",
                    "Je transmets à {business}, qui vous confirme et vous donne le tarif. Votre prénom et votre e-mail ?",
                ),
                ExampleTurn("user", "Paul Chevalier, paul.chevalier@example.com"),
                ExampleTurn("assistant", "Merci Paul, c'est transmis à {business}."),
            ),
        ),
    ),
    report=MonthlyStats(
        conversations=64,
        requests=21,
        quotes=8,
        appointments=9,
        urgent=0,
        photo_requests=0,
        handled=19,
        outside_hours_pct=61,
        languages=(),
        average_handling_hours=1.0,
        top_questions=(
            "Avez-vous des plats végétariens ?",
            "Faites-vous les anniversaires et les événements privés ?",
            "Acceptez-vous les titres-restaurant ?",
        ),
        won=7,
    ),
)

_PLUMBER = TradeExamples(
    requests=(
        ExampleRequest(
            type=AiAssistantRequestType.URGENT,
            status=AiAssistantRequestStatus.NEW,
            name="Nadia Petit",
            contact="06 39 98 01 23",
            summary="Fuite sous l'évier de la cuisine, l'eau coule dans le placard. Souhaite un passage rapide.",
            days_ago=1,
            received_at=time(22, 31),
            turns=(
                ExampleTurn(
                    "user",
                    "Bonsoir, j'ai une fuite sous l'évier de la cuisine, l'eau coule dans le placard. "
                    "Vous pouvez venir vite ?",
                ),
                ExampleTurn(
                    "assistant",
                    "Je transmets en urgence à {business}. Votre prénom et un téléphone, pour qu'on vous rappelle ?",
                ),
                ExampleTurn("user", "Nadia Petit, 06 39 98 01 23"),
                ExampleTurn(
                    "assistant", "C'est transmis en urgence, Nadia. {business} vous rappelle dès que possible."
                ),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.QUOTE,
            status=AiAssistantRequestStatus.HANDLED,
            name="Laura Faure",
            contact="06 39 98 34 12",
            summary="Robinet de la salle de bains qui goutte, même fermé. Souhaite le faire changer.",
            days_ago=4,
            received_at=time(14, 20),
            photo="plomberie",
            outcome=AiAssistantRequestOutcome.WON,
            turns=(
                ExampleTurn(
                    "user", "Bonjour, le robinet de la salle de bains goutte, même fermé. Vous pouvez le changer ?"
                ),
                ExampleTurn("assistant", "Je transmets à {business}. Pouvez-vous m'envoyer une photo du robinet ?"),
                _PHOTO_TURN,
                ExampleTurn("assistant", "Merci, la photo est jointe à votre demande. Votre prénom et un téléphone ?"),
                ExampleTurn("user", "Laura Faure, 06 39 98 34 12"),
                ExampleTurn("assistant", "Merci Laura, c'est transmis à {business}."),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.APPOINTMENT,
            status=AiAssistantRequestStatus.NEW,
            name="Olivier Blanc",
            contact="olivier.blanc@example.com",
            summary="Entretien annuel de la chaudière gaz. Souhaite un rendez-vous.",
            days_ago=2,
            received_at=time(9, 47),
            wished_half_days=2,
            turns=(
                ExampleTurn("user", "Bonjour, je voudrais faire l'entretien annuel de ma chaudière gaz."),
                ExampleTurn(
                    "assistant",
                    "Avec plaisir. Je note les demi-journées qui vous arrangent et votre e-mail : {business} vous "
                    "confirme l'heure.",
                ),
            ),
        ),
    ),
    report=MonthlyStats(
        conversations=47,
        requests=19,
        quotes=7,
        appointments=6,
        urgent=4,
        photo_requests=8,
        handled=17,
        outside_hours_pct=55,
        languages=(),
        average_handling_hours=2.0,
        top_questions=(
            "Intervenez-vous le week-end pour une fuite ?",
            "Faites-vous l'entretien des chaudières ?",
            "Quel délai pour changer un chauffe-eau ?",
        ),
        won=6,
    ),
)

_ANY_TRADE = TradeExamples(
    requests=(
        ExampleRequest(
            type=AiAssistantRequestType.QUESTION,
            status=AiAssistantRequestStatus.NEW,
            name="Claire Martin",
            contact="06 39 98 12 34",
            summary="Souhaite être rappelée pour un renseignement, de préférence en fin de journée.",
            days_ago=1,
            received_at=time(21, 5),
            turns=(
                ExampleTurn(
                    "user",
                    "Bonsoir, j'aurais besoin d'un renseignement. Quelqu'un peut me rappeler demain en fin de journée ?",
                ),
                ExampleTurn("assistant", "Avec plaisir, je transmets à {business}. Votre prénom et un téléphone ?"),
                ExampleTurn("user", "Claire Martin, 06 39 98 12 34"),
                ExampleTurn(
                    "assistant", "Merci Claire, c'est noté pour demain en fin de journée. {business} vous rappelle."
                ),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.QUOTE,
            status=AiAssistantRequestStatus.HANDLED,
            name="Sophie Leroy",
            contact="06 39 98 45 67",
            summary="Devis pour son entreprise, avec la facture au nom de la société.",
            days_ago=4,
            received_at=time(10, 5),
            outcome=AiAssistantRequestOutcome.WON,
            turns=(
                ExampleTurn(
                    "user",
                    "Bonjour, c'est pour mon entreprise : vous pouvez me faire un devis, avec la facture au nom de la "
                    "société ?",
                ),
                ExampleTurn(
                    "assistant", "Je transmets à {business}, qui vous rappelle pour en parler. À quel numéro ?"
                ),
                ExampleTurn("user", "Sophie Leroy, 06 39 98 45 67"),
                ExampleTurn("assistant", "Merci Sophie, c'est transmis à {business}."),
            ),
        ),
        ExampleRequest(
            type=AiAssistantRequestType.APPOINTMENT,
            status=AiAssistantRequestStatus.NEW,
            name="Julien Bernard",
            contact="julien.bernard@example.com",
            summary="Souhaite un rendez-vous, plutôt le matin.",
            days_ago=2,
            received_at=time(12, 10),
            wished_half_days=2,
            turns=(
                ExampleTurn("user", "Bonjour, je voudrais un rendez-vous, plutôt le matin si possible."),
                ExampleTurn(
                    "assistant",
                    "Avec plaisir. Je note les demi-journées qui vous arrangent et votre e-mail : {business} vous "
                    "confirme l'heure.",
                ),
            ),
        ),
    ),
    report=MonthlyStats(
        conversations=35,
        requests=12,
        quotes=5,
        appointments=3,
        urgent=1,
        photo_requests=2,
        handled=10,
        outside_hours_pct=50,
        languages=(),
        average_handling_hours=4.0,
        top_questions=(
            "Quels sont vos horaires le samedi ?",
            "Peut-on vous joindre le soir ?",
            "Faites-vous les devis gratuitement ?",
        ),
        won=3,
    ),
)

# The trades with examples of their own; every other trade reads ``_ANY_TRADE``.
_EXAMPLES_BY_TRADE: dict[AiAssistantTrade, TradeExamples] = {
    AiAssistantTrade.ROOFER: _ROOFER,
    AiAssistantTrade.CARPENTER: _CARPENTER,
    AiAssistantTrade.BODYWORK: _BODYWORK,
    AiAssistantTrade.GARAGE: _BODYWORK,
    AiAssistantTrade.RESTAURANT: _FOOD,
    AiAssistantTrade.FOOD_TRUCK: _FOOD,
    AiAssistantTrade.CATERER: _FOOD,
    AiAssistantTrade.PLUMBER: _PLUMBER,
}


class AiAssistantDemoSpaceExamples:
    """Builds the example requests and the example report of a demo space, for the business's trade."""

    def requests(
        self, assistant: AiAssistant, category: str | None, *, count: int, now: datetime
    ) -> list[AiAssistantDemoSpaceRequestItem]:
        """
        The first examples of the business's trade, dated from now and fitted to the business.

        The business's name fills the conversations, its opening hours tell which example came in while it was closed,
        and an appointment request wishes its next open half-days.

        Args:
            assistant: The demo receptionist.
            category: The business's Google Maps category, when known.
            count: How many examples to give (at most the trade's three).
            now: Current business time.

        Returns:
            The examples (``is_example``, negative ids), the waiting ones first, newest first, like the client space.
        """
        examples = list(enumerate(self._examples_of(category).requests[: max(count, 0)]))
        received = {position: self._received_moment(example, now) for position, example in examples}
        # Like the client space: the waiting ones first, the newest first among each.
        examples.sort(key=lambda entry: received[entry[0]], reverse=True)
        examples.sort(key=lambda entry: entry[1].status is not AiAssistantRequestStatus.NEW)
        opening_hours = AiAssistantAppointmentSlots.opening_hours_of(assistant)
        offered_days = AiAssistantAppointmentSlots.offer_for(assistant, today=now.date())
        return [
            self._request_item(
                position,
                example,
                assistant=assistant,
                received_at=received[position],
                received_outside_hours=OpeningHoursCalendar.received_outside_hours(opening_hours, received[position]),
                offered_days=offered_days,
                now=now,
            )
            for position, example in examples
        ]

    def report(self, assistant: AiAssistant, category: str | None, *, now: datetime) -> AiAssistantDemoSpaceReport:
        """
        The example report of the business's trade, for last month, read like a real one.

        Args:
            assistant: The demo receptionist.
            category: The business's Google Maps category, when known.
            now: Current business time.

        Returns:
            The report (``is_example``): the trade's example figures, in the receptionist's languages.
        """
        figures = replace(self._examples_of(category).report, languages=self._language_shares(assistant))
        last_month = now.date().replace(day=1) - timedelta(days=1)
        report = ai_assistant_client_space_payload.report_of_figures(figures, last_month, assistant.assistant_name)
        return AiAssistantDemoSpaceReport(**report.model_dump(), is_example=True)

    @staticmethod
    def _examples_of(category: str | None) -> TradeExamples:
        """The examples of the trade a Google Maps category reads as."""
        return _EXAMPLES_BY_TRADE.get(AiAssistantTradeResolver.of_category(category), _ANY_TRADE)

    @staticmethod
    def _received_moment(example: ExampleRequest, now: datetime) -> datetime:
        """When an example came in, in business time (naive)."""
        return datetime.combine(now.date() - timedelta(days=example.days_ago), example.received_at)

    def _request_item(
        self,
        position: int,
        example: ExampleRequest,
        *,
        assistant: AiAssistant,
        received_at: datetime,
        received_outside_hours: bool | None,
        offered_days: list[AppointmentDay],
        now: datetime,
    ) -> AiAssistantDemoSpaceRequestItem:
        """One example as the space lists it; its id is negative, so it never names a real request."""
        photo_url = self._showroom_photo_url(example.photo) if example.photo else None
        event_day = self._event_day(example.event, now.date()) if example.event else None
        texts = {
            "business": assistant.business_name,
            "event_day": self._spoken_day(event_day) if event_day else "",
        }
        return AiAssistantDemoSpaceRequestItem(
            id=-(position + 1),
            type=example.type,
            status=example.status,
            name=example.name,
            contact=example.contact,
            summary=example.summary,
            received_label=f"{received_at:%d/%m} à {received_at:%H:%M}",
            received_day=f"{received_at:%Y-%m-%d}",
            received_time=f"{received_at:%H:%M}",
            received_outside_hours=received_outside_hours,
            photo_urls=[photo_url] if photo_url else [],
            appointment_slots=[
                AiAssistantAppointmentSlots.label(AppointmentSlot(day=offered.day, period=offered.periods[0]))
                for offered in offered_days[: example.wished_half_days]
            ],
            outcome=example.outcome,
            event=(
                ai_assistant_client_space_payload.event(
                    {"date": event_day.isoformat(), "guests": example.event.guests, "budget": example.event.budget}
                )
                if example.event and event_day
                else None
            ),
            is_example=True,
            conversation=[
                AiAssistantTranscriptLine(
                    role=turn.role,
                    content=turn.text.format(**texts),
                    photo_url=photo_url if turn.is_photo else None,
                )
                for turn in example.turns
            ],
        )

    @staticmethod
    def _showroom_photo_url(photo: str) -> str:
        """The address of an example photo the demo host ships."""
        return f"{settings.demo_host_base_url.rstrip('/')}/showroom/examples/{photo}.jpg"

    @staticmethod
    def _event_day(event: ExampleEvent, today: date) -> date:
        """The Saturday an example event falls on: the first one at least ``weeks_ahead`` weeks after today."""
        earliest = today + timedelta(weeks=event.weeks_ahead)
        return earliest + timedelta(days=(5 - earliest.weekday()) % 7)

    @staticmethod
    def _spoken_day(day: date) -> str:
        """A day as a visitor writes it (« samedi 14 novembre »)."""
        weekday = FrenchDateFormatter.WEEKDAYS[day.weekday()]
        return f"{weekday} {FrenchDateFormatter.day_month(datetime.combine(day, time.min))}"

    @staticmethod
    def _language_shares(assistant: AiAssistant) -> tuple[LanguageShare, ...]:
        """The languages of the example month: the receptionist's first language, a tenth in its second one."""
        codes = [code for code in assistant.languages or [] if isinstance(code, str) and code]
        if not codes:
            return ()
        if len(codes) == 1:
            return (LanguageShare(code=codes[0], share_pct=100),)
        return (LanguageShare(code=codes[0], share_pct=90), LanguageShare(code=codes[1], share_pct=10))


ai_assistant_demo_space_examples = AiAssistantDemoSpaceExamples()
