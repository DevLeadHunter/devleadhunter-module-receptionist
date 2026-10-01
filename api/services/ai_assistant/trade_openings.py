"""
What a business's widget offers before the first message, by trade: three questions its customers ask, in French and
as they type them, and whether the photo-for-a-quote and appointment chips make sense for the trade.

The model writes each business's own questions (``suggested_questions``); a trade's questions stand in until it has.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from enums.ai_assistant_trade import AiAssistantTrade


@dataclass(frozen=True)
class OpeningSuggestions:
    """The chips under a widget's greeting: the questions offered, and the actions the trade offers beside them."""

    questions: tuple[str, ...]
    offers_photo_quote: bool
    offers_appointment: bool


class AiAssistantTradeOpenings:
    """The opening chips of each trade."""

    # Nothing to photograph for a quote: food, events, hair and beauty, real estate, health.
    _WITHOUT_PHOTO_QUOTE: ClassVar[frozenset[AiAssistantTrade]] = frozenset(
        {
            AiAssistantTrade.FOOD_TRUCK,
            AiAssistantTrade.CATERER,
            AiAssistantTrade.EVENT_VENUE,
            AiAssistantTrade.EVENT_SERVICE,
            AiAssistantTrade.HAIRDRESSER,
            AiAssistantTrade.BEAUTY,
            AiAssistantTrade.RESTAURANT,
            AiAssistantTrade.REAL_ESTATE,
            AiAssistantTrade.HEALTH,
        }
    )
    # No appointment to book: the food trades (a restaurant table is not a half-day slot).
    _WITHOUT_APPOINTMENT: ClassVar[frozenset[AiAssistantTrade]] = frozenset(
        {AiAssistantTrade.FOOD_TRUCK, AiAssistantTrade.CATERER, AiAssistantTrade.RESTAURANT}
    )
    _DEFAULT_QUESTIONS: ClassVar[tuple[str, ...]] = (
        "Quels services proposez-vous ?",
        "Comment obtenir un devis ?",
        "Quels sont vos horaires ?",
    )
    # Each trade's questions, the one its customers ask most first.
    _QUESTIONS: ClassVar[dict[AiAssistantTrade, tuple[str, ...]]] = {
        AiAssistantTrade.FOOD_TRUCK: (
            "Où êtes-vous cette semaine ?",
            "Je peux voir le menu ?",
            "Vous faites les mariages et les fêtes ?",
        ),
        AiAssistantTrade.CATERER: (
            "Vous faites les mariages ?",
            "Quel est votre prix par personne ?",
            "Je peux voir vos menus ?",
        ),
        AiAssistantTrade.EVENT_VENUE: (
            "Ma date de mariage est-elle libre ?",
            "Combien de personnes pouvez-vous accueillir ?",
            "Combien coûte la location de la salle ?",
        ),
        AiAssistantTrade.EVENT_SERVICE: (
            "Êtes-vous libre pour notre mariage ?",
            "Quels sont vos tarifs pour un mariage ?",
            "Vous vous déplacez dans toute la région ?",
        ),
        AiAssistantTrade.PLUMBER: (
            "Combien coûte une réparation de fuite ?",
            "Mon chauffe-eau ne marche plus, vous venez ?",
            "J'ai une fuite, vous pouvez venir vite ?",
        ),
        AiAssistantTrade.LOCKSMITH: (
            "Combien coûte un changement de serrure ?",
            "Ma porte a claqué, vous pouvez venir ?",
            "Vous posez des portes blindées ?",
        ),
        AiAssistantTrade.ELECTRICIAN: (
            "Combien coûte une mise aux normes ?",
            "Mon tableau disjoncte, vous pouvez venir ?",
            "Vous refaites l'électricité d'une maison ?",
        ),
        AiAssistantTrade.DOORS_AND_WINDOWS: (
            "Combien coûte une fenêtre sur mesure ?",
            "Mon volet roulant est bloqué, vous réparez ?",
            "Vous motorisez les portails ?",
        ),
        AiAssistantTrade.BODYWORK: (
            "Combien coûte la réparation d'une rayure ?",
            "Vous travaillez avec les assurances ?",
            "Vous avez un véhicule de prêt ?",
        ),
        AiAssistantTrade.GARAGE: (
            "Combien coûte une vidange ?",
            "Un voyant s'est allumé, je peux passer ?",
            "Vous réparez toutes les marques ?",
        ),
        AiAssistantTrade.CARPENTER: (
            "Combien coûte une extension en bois ?",
            "Ma charpente est abîmée, vous venez voir ?",
            "Vous faites les terrasses en bois ?",
        ),
        AiAssistantTrade.ROOFER: (
            "Combien coûte une réparation de toiture ?",
            "J'ai une fuite au toit, vous pouvez venir ?",
            "Vous faites le démoussage de toiture ?",
        ),
        AiAssistantTrade.JOINER: (
            "Combien coûte une porte d'entrée ?",
            "Vous faites des placards sur mesure ?",
            "Une fenêtre ferme mal, vous réparez ?",
        ),
        AiAssistantTrade.PAINTER: (
            "Combien coûte la peinture d'une pièce ?",
            "Vous faites aussi les façades ?",
            "Vous posez du papier peint ?",
        ),
        AiAssistantTrade.MASON: (
            "Combien coûte une dalle en béton ?",
            "Une fissure est apparue, vous venez voir ?",
            "Vous faites les extensions de maison ?",
        ),
        AiAssistantTrade.LANDSCAPER: (
            "Combien coûte l'entretien d'un jardin ?",
            "Vous faites la taille de haies ?",
            "Vous évacuez les déchets verts ?",
        ),
        AiAssistantTrade.HAIRDRESSER: (
            "Quels sont vos tarifs ?",
            "Vous avez de la place samedi ?",
            "Vous êtes ouverts le lundi ?",
        ),
        AiAssistantTrade.BEAUTY: (
            "Quels sont vos tarifs ?",
            "Vous avez de la place cette semaine ?",
            "Vous proposez des bons cadeaux ?",
        ),
        AiAssistantTrade.RESTAURANT: (
            "Je peux voir la carte ?",
            "Vous êtes ouverts ce soir ?",
            "Vous accueillez les groupes ?",
        ),
        AiAssistantTrade.REAL_ESTATE: (
            "Vous pouvez estimer ma maison ?",
            "Quels sont vos frais d'agence ?",
            "Vous avez des biens à louer ?",
        ),
        AiAssistantTrade.HEALTH: (
            "Vous prenez de nouveaux patients ?",
            "Combien coûte une consultation ?",
            "Vous avez une place cette semaine ?",
        ),
    }

    @classmethod
    def of(cls, trade: AiAssistantTrade) -> OpeningSuggestions:
        """
        The opening chips of a trade.

        Args:
            trade: The business's trade.

        Returns:
            Its questions and actions; an unknown trade (``OTHER``, most often a craftsman) gets general questions
            and both actions.
        """
        return OpeningSuggestions(
            questions=cls._QUESTIONS.get(trade, cls._DEFAULT_QUESTIONS),
            offers_photo_quote=trade not in cls._WITHOUT_PHOTO_QUOTE,
            offers_appointment=trade not in cls._WITHOUT_APPOINTMENT,
        )
