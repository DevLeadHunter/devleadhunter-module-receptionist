"""
What the receptionist never improvises: the sensitive subjects (prices, delays, warranties…) and the sentence the
business wants said on each. Every assistant has defaults; the business edits or switches them off from its space.
In the prompt they come right after the absolute rules, as imposed answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from models.ai_assistant import AiAssistant

# The subjects, in the order the space shows them: key, topic, default answer (« {business} » = the business).
DEFAULT_LIMITS: tuple[tuple[str, str, str], ...] = (
    (
        "price",
        "Prix et tarifs",
        "Je n'ai pas le tarif exact pour votre demande : {business} vous le précise. Laissez-moi vos "
        "coordonnées, avec une photo si c'est utile, on vous rappelle.",
    ),
    (
        "delay",
        "Délai d'intervention",
        "Je ne peux pas promettre une date : {business} vous confirme un créneau au rappel.",
    ),
    (
        "warranty",
        "Garantie et assurance",
        "Les garanties se précisent directement avec {business} : je note votre question pour qu'on vous réponde.",
    ),
    (
        "emergency",
        "Urgence hors horaires",
        "Décrivez-moi le problème et laissez votre numéro : je préviens {business} tout de suite, on vous "
        "rappelle au plus vite.",
    ),
    (
        "area",
        "Zone d'intervention",
        "Si votre adresse est loin de la zone habituelle, {business} vous dira au rappel si un déplacement est "
        "possible.",
    ),
    (
        "payment",
        "Paiement et acompte",
        "Les modalités de paiement se voient directement avec {business}.",
    ),
)


@dataclass(frozen=True)
class AssistantLimit:
    """One sensitive subject and the sentence said on it."""

    key: str
    topic: str
    answer: str
    enabled: bool = True
    # The business wrote this sentence itself: it is said as it is, even over the published information.
    is_custom: bool = False


class AiAssistantLimits:
    """The imposed answers of an assistant: the defaults, the business's edits, the prompt lines."""

    MAX_ANSWER_CHARS: ClassVar[int] = 300
    _TOPICS: ClassVar[dict[str, str]] = {key: topic for key, topic, _answer in DEFAULT_LIMITS}

    @classmethod
    def defaults(cls, business_name: str) -> list[AssistantLimit]:
        """
        The default answers, the business named.

        Args:
            business_name: The business.

        Returns:
            One limit per subject, all enabled.
        """
        return [
            AssistantLimit(key=key, topic=topic, answer=answer.replace("{business}", business_name))
            for key, topic, answer in DEFAULT_LIMITS
        ]

    @classmethod
    def effective(cls, assistant: AiAssistant) -> list[AssistantLimit]:
        """
        The assistant's limits as the prompt and the space read them: the business's edits over the defaults.

        Args:
            assistant: The assistant.

        Returns:
            One limit per subject, in the space's order.
        """
        stored = {
            str(item.get("key")): item
            for item in (assistant.limits_json or [])
            if isinstance(item, dict) and str(item.get("key")) in cls._TOPICS
        }
        limits: list[AssistantLimit] = []
        for default in cls.defaults(assistant.business_name):
            item = stored.get(default.key)
            if item is None:
                limits.append(default)
                continue
            typed = cls._clean_answer(item.get("answer"))
            limits.append(
                AssistantLimit(
                    key=default.key,
                    topic=default.topic,
                    answer=typed or default.answer,
                    enabled=bool(item.get("enabled", True)),
                    is_custom=bool(typed) and typed != default.answer,
                )
            )
        return limits

    @classmethod
    def clean(cls, updates: list[dict[str, Any]], business_name: str) -> list[dict[str, Any]]:
        """
        What to store from the business's edits: known subjects only, answers bounded. A sentence left as proposed
        is not stored (it follows the default, even when its wording changes); an untouched subject is not stored.

        Args:
            updates: The edits, as ``{"key", "answer", "enabled"}`` dicts.
            business_name: The business, to recognise the proposed sentences.

        Returns:
            The JSON to keep on the assistant.
        """
        proposed = {limit.key: limit.answer for limit in cls.defaults(business_name)}
        kept: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in updates:
            key = str(item.get("key", ""))
            if key not in cls._TOPICS or key in seen:
                continue
            seen.add(key)
            answer = cls._clean_answer(item.get("answer"))
            if answer == proposed[key]:
                answer = ""
            enabled = bool(item.get("enabled", True))
            if answer or not enabled:
                kept.append({"key": key, "answer": answer, "enabled": enabled})
        return kept

    @staticmethod
    def prompt_lines(limits: list[AssistantLimit]) -> list[str]:
        """
        The prompt block of the enabled limits: the business's own sentences as they are, the defaults only
        when the published information says nothing on the subject.

        Args:
            limits: The assistant's limits.

        Returns:
            The lines to add to the system prompt; empty when every subject is switched off.
        """
        enabled = [limit for limit in limits if limit.enabled and limit.answer]
        if not enabled:
            return []
        lines = [
            "SUJETS SENSIBLES (quand un visiteur en parle ; jamais un chiffre, une date ou un engagement de plus "
            "que ce qui suit ou que les informations ci-dessous) :"
        ]
        for limit in enabled:
            if limit.is_custom:
                lines.append(f"- {limit.topic} : réponds avec les mots de l'entreprise : « {limit.answer} »")
            else:
                lines.append(
                    f"- {limit.topic} : si l'information ne figure pas ci-dessous, dis en substance : "
                    f"« {limit.answer} »"
                )
        return lines

    @classmethod
    def _clean_answer(cls, value: Any) -> str:
        """A typed answer on one line, bounded."""
        return " ".join(str(value or "").split())[: cls.MAX_ANSWER_CHARS]


ai_assistant_limits = AiAssistantLimits()
