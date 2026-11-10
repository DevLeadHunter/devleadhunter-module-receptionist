"""
The trade of a business, read from its Google Maps category: the receptionist module's one table of trade keywords.

Each feature keeps its own data by trade (the demo page's request volume, the event intake, the widget's opening
chips); only this table reads the words of the category.
"""

from __future__ import annotations

import re
from typing import ClassVar

from enums.ai_assistant_trade import AiAssistantTrade
from services.text_normalizer import TextNormalizer


def _word_starts(*starts: str) -> re.Pattern[str]:
    """A pattern matching a word of a folded category that begins with one of the starts (several words allowed)."""
    return re.compile(r"\b(?:" + "|".join(re.escape(start) for start in starts) + ")")


class AiAssistantTradeResolver:
    """Finds a business's trade from the words of its Google Maps category."""

    # Accent-free word starts, checked in order: the first trade with a word of the category starting so wins.
    _TRADES: ClassVar[tuple[tuple[AiAssistantTrade, re.Pattern[str]], ...]] = (
        # First: a food truck that caters stays a food truck, a caterer is an event trade before being a restaurant.
        (AiAssistantTrade.FOOD_TRUCK, _word_starts("food")),
        (AiAssistantTrade.CATERER, _word_starts("traiteur")),
        (
            AiAssistantTrade.EVENT_VENUE,
            _word_starts("mariage", "wedding", "banquet", "recept", "evenement", "seminaire"),
        ),
        (AiAssistantTrade.EVENT_SERVICE, _word_starts("orchestre", "photographe")),
        (AiAssistantTrade.PLUMBER, _word_starts("plomb", "chauffag", "sanitaire")),
        (AiAssistantTrade.LOCKSMITH, _word_starts("serrur")),
        (AiAssistantTrade.ELECTRICIAN, _word_starts("electric")),
        # Before the garages: « Installateur de portes de garage » fits doors, not cars.
        (AiAssistantTrade.DOORS_AND_WINDOWS, _word_starts("porte", "portail", "fenetre", "volet")),
        (AiAssistantTrade.BODYWORK, _word_starts("carross")),
        (AiAssistantTrade.GARAGE, _word_starts("garag", "mecani", "automobile", "pneu")),
        # Before the roofers: a « Charpentier couvreur » is a carpenter first.
        (AiAssistantTrade.CARPENTER, _word_starts("charpent")),
        (AiAssistantTrade.ROOFER, _word_starts("couvr", "toiture", "zingu")),
        (AiAssistantTrade.JOINER, _word_starts("menuis", "ebenist")),
        (AiAssistantTrade.PAINTER, _word_starts("peintre", "peinture")),
        (AiAssistantTrade.MASON, _word_starts("macon", "renovation", "batiment", "construction")),
        (
            AiAssistantTrade.LANDSCAPER,
            _word_starts("paysag", "jardinier", "jardinage", "entretien de jardin", "espaces verts", "elag"),
        ),
        (AiAssistantTrade.HAIRDRESSER, _word_starts("coiff", "barbier", "barber")),
        (AiAssistantTrade.BEAUTY, _word_starts("esthetic", "beaute", "onglerie")),
        (
            AiAssistantTrade.RESTAURANT,
            _word_starts(
                "restaurant",
                "restauration rapide",
                "pizz",
                "brasserie",
                "creperie",
                "bistro",
                "snack",
                "kebab",
                "burger",
                "friterie",
                "rotisserie",
                "sushi",
            ),
        ),
        (AiAssistantTrade.REAL_ESTATE, _word_starts("immobili")),
        (AiAssistantTrade.HEALTH, _word_starts("dentist", "kine", "osteo", "medecin", "podolog")),
    )

    @classmethod
    def of_category(cls, category: str | None) -> AiAssistantTrade:
        """
        The trade of a business.

        Args:
            category: Its Google Maps category (« Plombier chauffagiste », « Food truck »), or None.

        Returns:
            The first matching trade, else ``AiAssistantTrade.OTHER``.
        """
        words = " ".join(re.findall(r"[a-z0-9]+", TextNormalizer.fold(category or "")))
        for trade, pattern in cls._TRADES:
            if pattern.search(words):
                return trade
        return AiAssistantTrade.OTHER
