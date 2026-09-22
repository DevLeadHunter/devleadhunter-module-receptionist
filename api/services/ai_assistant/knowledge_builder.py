"""Build an AI assistant's grounded knowledge base and system prompt from a prospect's data.

The knowledge base is the assistant's single source of truth: the model answers only from it and
never invents a price, an availability or a fact that is not in it (the anti-hallucination contract).
It is built from the same enrichment that feeds the demo sites, so a prospect's assistant knows what
his site shows.
"""

from typing import Any

from services.templates.site_content import (
    _clean_opening_hours,
    _clean_review_text,
    format_rating_value,
    format_review_count,
)

MAX_REVIEWS = 6
MAX_REVIEW_CHARS = 280
MAX_SERVICES = 20

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
    ) -> str:
        """Render the French system prompt that grounds the assistant on ``knowledge``.

        Args:
            knowledge: The knowledge base from :meth:`build_knowledge`.
            assistant_name: The assistant's display name (e.g. "Sofia").
            languages: Active language ISO codes; the assistant still replies in the visitor's language.
            tone: Optional persona tone hint injected into the prompt.

        Returns:
            The system prompt string.
        """
        identity = knowledge.get("identity", {})
        business_name = identity.get("business_name", "l'entreprise")
        location = identity.get("city")
        header = f"Tu es {assistant_name}, l'assistante virtuelle de {business_name}"
        header += f", à {location}." if location else "."

        lines = [
            header,
            "",
            "RÈGLES ABSOLUES :",
            "- Réponds UNIQUEMENT à partir des informations ci-dessous. N'invente jamais un prix, une "
            "disponibilité, un horaire ou un fait qui n'y figure pas.",
            "- Si tu ne connais pas une information, dis-le simplement et propose de transmettre la "
            "demande à un conseiller (recueille alors le nom et un moyen de recontact).",
            f"- {self._languages_line(languages)}",
            "- Sois chaleureuse, professionnelle et CONCISE (2 à 4 phrases). Une seule question à la fois.",
            "- Cherche à qualifier le besoin, puis propose une action concrète (visite, rendez-vous, "
            "rappel, estimation).",
        ]
        if tone:
            lines.append(f"- Ton : {tone}.")

        lines.append("")
        lines.extend(self._identity_lines(identity))
        rating_line = self._rating_line(knowledge.get("rating"))
        if rating_line:
            lines.append(rating_line)
        lines.extend(self._hours_lines(knowledge.get("opening_hours")))
        lines.extend(self._services_lines(knowledge.get("services")))
        lines.extend(self._reviews_lines(knowledge.get("reviews")))

        lines.append("")
        lines.append("Tu accueilles maintenant un visiteur du site.")
        return "\n".join(lines)

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
            "Détecte la langue du message du visiteur et réponds INTÉGRALEMENT dans cette seule langue, "
            "sans jamais mélanger deux langues dans une même réponse."
        )
        if names:
            offered = ", ".join(names)
            return f"{base} Langues fréquentes ici : {offered}."
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
