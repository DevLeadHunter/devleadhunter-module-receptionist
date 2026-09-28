"""
What a visitor's quote photo shows, read by a vision model: the object, the damage, how urgent it looks and what is
missing to quote it — never a price. When the model's reply breaks a rule (a price, an empty text), the visitor
reads ours.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, ClassVar

from enums.ai_assistant_photo import AiAssistantPhotoUrgency
from enums.assistant_llm import AssistantLlmUsage
from services.ai_assistant.field_limits import SHORT_TEXT_MAX_CHARS
from services.ai_assistant.knowledge_builder import LANGUAGE_NAMES
from services.ai_assistant.llm_router import assistant_llm_router

logger = logging.getLogger(__name__)

_MAX_REPLY_CHARS = 600


@dataclass(frozen=True)
class PhotoAnalysis:
    """What the vision model saw in a photo, and what the assistant answers the visitor."""

    is_relevant: bool | None
    object_label: str | None
    damage: str | None
    urgency: AiAssistantPhotoUrgency | None
    missing_questions: tuple[str, ...]
    reply: str


class AiAssistantPhotoVision:
    """Asks the vision model what a visitor's photo shows, to prepare a quote — never a price."""

    SYSTEM_PROMPT: ClassVar[str] = (
        "Tu es l'assistante virtuelle d'une entreprise. Un visiteur de son site t'envoie une photo pour "
        "obtenir un devis. Le métier de l'entreprise t'est donné : juge la photo AVEC CE MÉTIER en tête. "
        "Regarde la photo et réponds UNIQUEMENT par un objet JSON :\n"
        '{"relevant": true|false, "object": "…", "damage": "…", "urgency": "low"|"medium"|"high", '
        '"missing_questions": ["…"], "reply": "…"}\n'
        "- relevant : true dès que la photo peut aider à comprendre le besoin d'un client de ce métier. "
        "Pour un métier manuel, c'est l'objet ou le lieu du problème (toit, fuite, voiture, jardin, plat, "
        "pièce à rénover…). Pour un métier du numérique ou du service (agence web, développeur, graphiste, "
        "photographe, comptable…), c'est aussi bien un écran, une capture de site ou d'application, un "
        "logo, une maquette, un message d'erreur ou un document : un client montre son site actuel ou "
        "celui qu'il veut, c'est son besoin. false seulement si la photo n'a aucun rapport avec le métier "
        "(selfie, paysage, image choquante…).\n"
        "- object : ce qui est photographié, en quelques mots (ex. « aile avant gauche d'une voiture », "
        "« page d'accueil d'un site vitrine, vue sur tablette »).\n"
        "- damage : le problème ou le besoin visible, factuel (ex. « rayure profonde, peinture à refaire », "
        "« site daté, texte peu lisible, pas de bouton de contact ») ; vide si tu ne vois rien à améliorer.\n"
        "- urgency : high seulement pour un risque immédiat (fuite active, câble à nu, structure qui "
        "cède, site ou boutique en ligne hors service) ; medium si ça peut s'aggraver ; low sinon.\n"
        "- missing_questions : 1 ou 2 questions courtes, indispensables pour chiffrer (dimensions, "
        "accès, matériau, nombre de pages, ce qui doit changer…).\n"
        "- reply : 2 ou 3 phrases au visiteur, dans la langue demandée : ce que tu vois, dit avec les mots "
        "du métier (un développeur parle du site montré, pas de l'écran qui l'affiche), les questions "
        "manquantes, puis l'invitation à laisser son prénom et un téléphone pour recevoir le devis. Si "
        "la photo est hors sujet : refus poli, en invitant à envoyer une photo de ce dont il a besoin.\n"
        "Règles absolues : JAMAIS de prix, de fourchette, de coût ni de délai d'intervention — le devis "
        "est établi par l'entreprise. Ne décris pas les personnes. Ne diagnostique que ce qui est visible."
    )
    # Written by us, per widget language, when the model is unavailable or breaks a rule.
    FALLBACK_REPLIES: ClassVar[dict[str, str]] = {
        "fr": (
            "Merci pour la photo, je la transmets pour votre devis. Décrivez-moi le problème en quelques "
            "mots, et laissez-moi votre prénom et un téléphone pour être recontacté."
        ),
        "nl": (
            "Bedankt voor de foto, ik geef hem door voor uw offerte. Beschrijf het probleem in een paar "
            "woorden en laat uw voornaam en telefoonnummer achter, dan nemen we contact op."
        ),
        "en": (
            "Thank you for the photo, I am passing it on for your quote. Describe the problem in a few "
            "words and leave your first name and a phone number so we can get back to you."
        ),
        "de": (
            "Danke für das Foto, ich leite es für Ihr Angebot weiter. Beschreiben Sie das Problem kurz und "
            "hinterlassen Sie Ihren Vornamen und eine Telefonnummer, damit wir Sie kontaktieren."
        ),
        "lb": (
            "Merci fir d'Foto, ech ginn se fir Ären Devis weider. Beschreift de Problem a puer Wierder a "
            "loosst Äre Virnumm an eng Telefonsnummer, da mellen mir eis."
        ),
    }
    OFF_TOPIC_REPLIES: ClassVar[dict[str, str]] = {
        "fr": "Je ne vois pas sur cette photo de quoi préparer un devis. Envoyez-moi une photo du problème.",
        "nl": "Op deze foto zie ik niets om een offerte voor te maken. Stuur me een foto van het probleem.",
        "en": "I can't see anything to quote on this photo. Please send me a photo of the problem.",
        "de": "Auf diesem Foto sehe ich nichts für ein Angebot. Schicken Sie mir bitte ein Foto des Problems.",
        "lb": "Op dëser Foto gesinn ech näischt fir en Devis. Schéckt mer w.e.g. eng Foto vum Problem.",
    }
    # A figure with a currency, either way round (« 250 € », « EUR 250 », « 250,- Euro », « CHF 90 »):
    # nothing shown to the visitor may carry a price.
    PRICE_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:€|\bchf|\beur(?:os?)?)\s?\d|\d[\d\s.,]*-?\s?(?:€|\b(?:eur|euros?|chf)\b)", re.IGNORECASE
    )
    _YES: ClassVar[frozenset[bool | int | str]] = frozenset({True, "true", "yes", "oui", "1"})
    _NO: ClassVar[frozenset[bool | int | str]] = frozenset({False, "false", "no", "non", "0"})

    async def describe(
        self, *, url: str, business_name: str, trade: str | None, language: str | None, eu_only: bool = False
    ) -> PhotoAnalysis:
        """
        Ask the vision model about a photo (Mistral first, see ``llm_router``).

        Args:
            url: Public URL of the stored photo.
            business_name: The business the visitor asks.
            trade: Its trade (the prospect category), to judge what is on-topic.
            language: The widget language, for the reply.
            eu_only: The assistant only allows Mistral (no Groq fallback).

        Returns:
            The analysis; a neutral one (``is_relevant`` None) when no model is available.
        """
        context = (
            f"Entreprise : {business_name}" + (f" ({trade})" if trade else "") + ". "
            f"Réponds au visiteur en {LANGUAGE_NAMES[self._lang(language)]}."
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [{"type": "text", "text": context}, {"type": "image_url", "image_url": {"url": url}}],
            },
        ]
        try:
            answer = await assistant_llm_router.complete_json(
                AssistantLlmUsage.VISION, messages, eu_only=eu_only, max_tokens=700, temperature=0.2, timeout=60.0
            )
        except Exception:
            logger.warning("Vision call failed for a photo", exc_info=True)
            answer = None
        return self.parse(answer, language)

    @classmethod
    def parse(cls, answer: dict[str, Any] | None, language: str | None) -> PhotoAnalysis:
        """
        Validate the model's answer, keeping only what honours the contract.

        Args:
            answer: The parsed JSON, or None when the model failed.
            language: The widget language, for our own wording.

        Returns:
            The analysis; our own reply replaces one that is empty or quotes a price, and a description
            quoting a price is dropped.
        """
        if not isinstance(answer, dict):
            return cls.fallback(language)
        lang = cls._lang(language)
        is_relevant = cls._verdict(answer.get("relevant"))
        if is_relevant is False:
            reply = cls._text(answer.get("reply"), _MAX_REPLY_CHARS)
            safe = reply if reply and not cls.PRICE_PATTERN.search(reply) else cls.OFF_TOPIC_REPLIES[lang]
            return PhotoAnalysis(False, None, None, None, (), safe)
        urgency_value = answer.get("urgency")
        urgency_text = urgency_value.strip().lower() if isinstance(urgency_value, str) else None
        urgency = (
            AiAssistantPhotoUrgency(urgency_text)
            if urgency_text in {level.value for level in AiAssistantPhotoUrgency}
            else None
        )
        raw_questions = answer.get("missing_questions")
        questions = (
            cls._text(raw_question, SHORT_TEXT_MAX_CHARS)
            for raw_question in (raw_questions if isinstance(raw_questions, list) else [])
        )
        missing = tuple(question for question in questions if question and not cls.PRICE_PATTERN.search(question))[:2]
        reply = cls._text(answer.get("reply"), _MAX_REPLY_CHARS)
        if not reply or cls.PRICE_PATTERN.search(reply):
            reply = cls.FALLBACK_REPLIES[lang]
        return PhotoAnalysis(
            is_relevant=is_relevant,
            object_label=cls._without_price(cls._text(answer.get("object"), SHORT_TEXT_MAX_CHARS)),
            damage=cls._without_price(cls._text(answer.get("damage"), SHORT_TEXT_MAX_CHARS)),
            urgency=urgency,
            missing_questions=missing,
            reply=reply,
        )

    @classmethod
    def fallback(cls, language: str | None) -> PhotoAnalysis:
        """
        The analysis used when the model cannot look at the photo: kept, unjudged, a neutral reply.

        Args:
            language: The widget language.

        Returns:
            A neutral analysis.
        """
        return PhotoAnalysis(None, None, None, None, (), cls.FALLBACK_REPLIES[cls._lang(language)])

    @classmethod
    def _lang(cls, language: str | None) -> str:
        """A supported widget language (French by default)."""
        code = (language or "").strip().lower()[:2]
        return code if code in cls.FALLBACK_REPLIES else "fr"

    @classmethod
    def _without_price(cls, text: str | None) -> str | None:
        """A description, dropped when it slips in a price."""
        return None if text and cls.PRICE_PATTERN.search(text) else text

    @classmethod
    def _verdict(cls, value: Any) -> bool | None:
        """The on-topic verdict read leniently (« false », "0"…); None when the model gave none."""
        normalized = value.strip().lower() if isinstance(value, str) else value
        if isinstance(normalized, bool | str):
            if normalized in cls._YES:
                return True
            if normalized in cls._NO:
                return False
        if isinstance(normalized, int):
            return bool(normalized)
        return None

    @staticmethod
    def _text(value: Any, max_chars: int) -> str | None:
        """A trimmed, bounded string, or None."""
        if not isinstance(value, str):
            return None
        cleaned = " ".join(value.split())
        return cleaned[:max_chars] or None
