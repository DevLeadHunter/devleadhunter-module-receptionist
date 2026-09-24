"""Build an AI assistant's grounded knowledge base and system prompt from a prospect's data.

The knowledge base is the assistant's single source of truth: the model answers only from it and
never invents a price, an availability or a fact that is not in it (the anti-hallucination contract).
It is built from the same enrichment that feeds the demo sites, so a prospect's assistant knows what
his site shows.
"""

from datetime import UTC, datetime
from typing import Any

from enums.ai_assistant_persona_gender import AiAssistantPersonaGender
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.french_date_formatter import FrenchDateFormatter
from services.templates.site_content import (
    _clean_opening_hours,
    _clean_review_text,
    format_rating_value,
    format_review_count,
)

MAX_REVIEWS = 6
MAX_REVIEW_CHARS = 280
MAX_SERVICES = 20

try:  # Every targeted country (FR, BE, LU, CH) keeps Paris time; naive UTC when tzdata is missing.
    from zoneinfo import ZoneInfo

    _BUSINESS_TIMEZONE: ZoneInfo | None = ZoneInfo("Europe/Paris")
except Exception:
    _BUSINESS_TIMEZONE = None

_WORDING_BY_GENDER: dict[AiAssistantPersonaGender, dict[str, str]] = {
    AiAssistantPersonaGender.FEMININE: {
        "role": "l'assistante virtuelle",
        "first_person": "féminin (« je suis ravie », « désolée »)",
        "style": "chaleureuse, humaine et confiante",
        "concise": "CONCISE",
    },
    AiAssistantPersonaGender.MASCULINE: {
        "role": "l'assistant virtuel",
        "first_person": "masculin (« je suis ravi », « désolé »)",
        "style": "chaleureux, humain et confiant",
        "concise": "CONCIS",
    },
}

# ISO code → French language name, for the multilingual line of the system prompt.
_LANGUAGE_NAMES: dict[str, str] = {
    "fr": "français",
    "en": "anglais",
    "de": "allemand",
    "lu": "luxembourgeois",
    "nl": "néerlandais",
    "it": "italien",
    "es": "espagnol",
    "pt": "portugais",
}


class AiAssistantKnowledgeBuilder:
    """Turns a prospect's identity and enrichment into a grounded knowledge base and system prompt."""

    def build_knowledge(
        self,
        *,
        business_name: str,
        city: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        enrichment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble the grounded knowledge base an assistant answers from.

        Args:
            business_name: The prospect's business name.
            city: The prospect's city, when known.
            address: The prospect's street address, when known.
            phone: The public phone number, when known.
            email: The public email, when known.
            enrichment: The enrichment dict (``enrichment_service.to_dict``), or None.

        Returns:
            The knowledge base as a plain dict, ready to store on ``AiAssistant.knowledge_json``.
        """
        enr = enrichment or {}
        return {
            "identity": {
                "business_name": business_name,
                "city": city or None,
                "address": address or None,
                "phone": phone or None,
                "email": email or None,
                "description": self._clean_text(enr.get("description")),
            },
            "rating": self._build_rating(enr),
            "opening_hours": _clean_opening_hours(enr.get("opening_hours") or []),
            "services": self._build_services(enr.get("services")),
            "reviews": self._build_reviews(enr.get("reviews")),
            "social": {key: value for key, value in (enr.get("social_links") or {}).items() if value},
        }

    def render_system_prompt(
        self,
        knowledge: dict[str, Any],
        *,
        assistant_name: str,
        languages: list[str] | None = None,
        tone: str | None = None,
        now: datetime | None = None,
    ) -> str:
        """Render the French system prompt that grounds the assistant on ``knowledge``.

        Args:
            knowledge: The knowledge base from :meth:`build_knowledge`.
            assistant_name: The assistant's display name (e.g. "Sofia"); its gender drives the wording.
            languages: Active language ISO codes; the assistant still replies in the visitor's language.
            tone: Optional persona tone hint injected into the prompt.
            now: The business's current local time; defaults to the clock in the business timezone.

        Returns:
            The system prompt string.
        """
        identity = knowledge.get("identity", {})
        business_name = identity.get("business_name", "l'entreprise")
        location = identity.get("city")
        wording = _WORDING_BY_GENDER[ai_assistant_config_builder.resolve_persona_gender(assistant_name)]
        header = f"Tu es {assistant_name}, {wording['role']} de {business_name}"
        header += f", à {location}." if location else "."

        lines = [
            header,
            "",
            "RÈGLES ABSOLUES :",
            "- Réponds UNIQUEMENT à partir des informations ci-dessous. N'invente JAMAIS un prix, un "
            "horaire, une disponibilité ou un fait qui n'y figure pas — c'est la règle la plus importante.",
            "- Ne laisse JAMAIS entendre qu'un service absent des informations ci-dessous existe ou « peut "
            "s'étudier » (livraison, réservation, paiement en ligne, devis gratuit, garantie, urgence…) : tu "
            "ne t'engages à rien à la place de l'entreprise. Dis que tu ne sais pas et propose un rappel "
            "pour le confirmer.",
            f"- {self._languages_line(languages)}",
            f"- Tu parles de toi au {wording['first_person']}.",
            "- Sois d'abord VRAIMENT utile : réponds concrètement avec ce que tu sais et, quand c'est "
            "pertinent, un conseil simple du métier — sans jamais promettre un prix ni un délai.",
            "- Si une information manque (prix, horaire, disponibilité, prestation), dis-le avec naturel et "
            "propose de noter la demande pour que l'entreprise rappelle, en variant tes formulations — "
            "jamais deux fois la même phrase toute faite.",
            "- Fais avancer la conversation : UNE seule question à la fois pour cerner le besoin, puis "
            "propose UNE action concrète parmi ce que l'entreprise propose réellement ci-dessous, ou à défaut "
            "d'être rappelé. Pour recontacter quelqu'un, demande son prénom et un téléphone ou un e-mail.",
            f"- Style : {wording['style']}, comme un excellent accueil en personne. Reste "
            f"{wording['concise']} (2 à 4 phrases), sans jargon ni liste à puces. Mets en valeur ce qui "
            "distingue la maison quand c'est utile.",
        ]
        if tone:
            lines.append(f"- Ton : {tone}.")

        lines.append("")
        lines.extend(self._identity_lines(identity))
        rating_line = self._rating_line(knowledge.get("rating"))
        if rating_line:
            lines.append(rating_line)
        lines.append(self._today_line(now or self._business_now()))
        lines.extend(self._hours_lines(knowledge.get("opening_hours")))
        lines.extend(self._services_lines(knowledge.get("services")))
        lines.extend(self._reviews_lines(knowledge.get("reviews")))

        lines.append("")
        lines.append(
            "Tu accueilles maintenant un visiteur du site. Rappel : toute ta réponse, y compris la "
            "dernière phrase, est écrite dans la langue de son message."
        )
        return "\n".join(lines)

    @staticmethod
    def _business_now() -> datetime:
        return datetime.now(_BUSINESS_TIMEZONE) if _BUSINESS_TIMEZONE else datetime.now(UTC)

    def _today_line(self, moment: datetime) -> str:
        return (
            f"AUJOURD'HUI : {FrenchDateFormatter.long_date(moment)}, il est {moment:%H:%M} (heure locale de "
            "l'entreprise). Pour « ouvert maintenant / aujourd'hui », compare cette date et cette heure aux "
            "HORAIRES ci-dessous ; sans horaires, dis que tu ne sais pas."
        )

    def _build_rating(self, enr: dict[str, Any]) -> dict[str, str] | None:
        value = format_rating_value(enr.get("rating"))
        if not value:
            return None
        rating: dict[str, str] = {"value": value}
        count = format_review_count(enr.get("reviews_count"))
        if count:
            rating["count"] = count
        return rating

    def _build_services(self, raw_services: Any) -> list[str]:
        seen: set[str] = set()
        services: list[str] = []
        for name in raw_services or []:
            if not isinstance(name, str):
                continue
            clean = " ".join(name.split()).strip()
            key = clean.lower()
            if clean and key not in seen:
                seen.add(key)
                services.append(clean)
            if len(services) >= MAX_SERVICES:
                break
        return services

    def _build_reviews(self, raw_reviews: Any) -> list[dict[str, Any]]:
        reviews: list[dict[str, Any]] = []
        for review in raw_reviews or []:
            if not isinstance(review, dict):
                continue
            raw_text = review.get("text")
            if not isinstance(raw_text, str) or not raw_text.strip():
                continue
            text = _clean_review_text(raw_text)[:MAX_REVIEW_CHARS].strip()
            if not text:
                continue
            entry: dict[str, Any] = {"text": text}
            author = self._clean_text(review.get("author"))
            if author:
                entry["author"] = author
            if isinstance(review.get("rating"), (int, float)):
                entry["rating"] = review["rating"]
            reviews.append(entry)
            if len(reviews) >= MAX_REVIEWS:
                break
        return reviews

    def _languages_line(self, languages: list[str] | None) -> str:
        names = [_LANGUAGE_NAMES.get(code, code) for code in (languages or []) if code]
        base = (
            "LANGUE : réponds INTÉGRALEMENT dans la langue du message du visiteur — du premier au dernier "
            "mot — même si ce n'est pas une des langues habituelles de la maison. Ne mélange JAMAIS deux "
            "langues dans une même réponse."
        )
        if names:
            offered = ", ".join(names)
            return f"{base} (Langues les plus fréquentes ici : {offered}.)"
        return base

    def _identity_lines(self, identity: dict[str, Any]) -> list[str]:
        lines = [f"ENTREPRISE : {identity.get('business_name', '')}."]
        contact_bits = [bit for bit in (identity.get("phone"), identity.get("email"), identity.get("address")) if bit]
        if contact_bits:
            lines.append("CONTACT : " + " · ".join(contact_bits) + ".")
        description = identity.get("description")
        if description:
            lines.append(f"À PROPOS : {description}")
        return lines

    def _rating_line(self, rating: dict[str, Any] | None) -> str | None:
        if not rating or not rating.get("value"):
            return None
        count = rating.get("count")
        return f"NOTE GOOGLE : {rating['value']}" + (f" ({count} avis)." if count else ".")

    def _hours_lines(self, hours: list[dict[str, Any]] | None) -> list[str]:
        if not hours:
            return ["HORAIRES : non communiqués — propose de contacter l'entreprise pour les confirmer."]
        rows = [f"{row.get('day', '')} : {row.get('hours', '')}".strip() for row in hours if row.get("day")]
        return ["HORAIRES :", *(f"- {row}" for row in rows)] if rows else []

    def _services_lines(self, services: list[str] | None) -> list[str]:
        if not services:
            return []
        return ["SERVICES : " + ", ".join(services) + "."]

    def _reviews_lines(self, reviews: list[dict[str, Any]] | None) -> list[str]:
        if not reviews:
            return []
        lines = ["AVIS CLIENTS (pour le ton, ne pas les citer mot à mot) :"]
        for review in reviews:
            author = f" — {review['author']}" if review.get("author") else ""
            lines.append(f'- "{review["text"]}"{author}')
        return lines

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        clean = " ".join(value.split()).strip()
        return clean or None


ai_assistant_knowledge_builder = AiAssistantKnowledgeBuilder()
