"""How a prospecting email or SMS names the receptionist: in the gender of the first name it carries.

The casting mixes first names (Sofia, Léa, Inès, Hugo, Marc, Nathan), so a template never writes the
gendered words itself: « {prenom_receptionniste}, {assistant_virtuel} (IA) » reads « Léa, une assistante
virtuelle (IA) » or « Nathan, un assistant virtuel (IA) ». The gender is the one the persona speaks in,
resolved from the configured first name.
"""

from __future__ import annotations

from typing import ClassVar

from enums.ai_assistant_persona_gender import AiAssistantPersonaGender
from models.ai_assistant import AiAssistant
from services.ai_assistant.config_builder import ai_assistant_config_builder


class ReceptionistWording:
    """The gendered noun phrases behind the ``{receptionniste}`` and ``{assistant_virtuel}`` variables."""

    _RECEPTIONIST: ClassVar[dict[AiAssistantPersonaGender, str]] = {
        AiAssistantPersonaGender.FEMININE: "une réceptionniste",
        AiAssistantPersonaGender.MASCULINE: "un réceptionniste",
    }
    _VIRTUAL_ASSISTANT: ClassVar[dict[AiAssistantPersonaGender, str]] = {
        AiAssistantPersonaGender.FEMININE: "une assistante virtuelle",
        AiAssistantPersonaGender.MASCULINE: "un assistant virtuel",
    }

    @classmethod
    def receptionist(cls, assistant: AiAssistant | None) -> str:
        """
        Resolve ``{receptionniste}``: « une réceptionniste » or « un réceptionniste ».

        Args:
            assistant: The sender's active assistant for the prospect, or None.

        Returns:
            The phrase agreed with the persona's first name, empty without an assistant.
        """
        if assistant is None:
            return ""
        return cls._RECEPTIONIST[ai_assistant_config_builder.resolve_persona_gender(assistant.assistant_name)]

    @classmethod
    def virtual_assistant(cls, assistant: AiAssistant | None) -> str:
        """
        Resolve ``{assistant_virtuel}``: « une assistante virtuelle » or « un assistant virtuel ».

        Args:
            assistant: The sender's active assistant for the prospect, or None.

        Returns:
            The phrase agreed with the persona's first name, empty without an assistant.
        """
        if assistant is None:
            return ""
        return cls._VIRTUAL_ASSISTANT[ai_assistant_config_builder.resolve_persona_gender(assistant.assistant_name)]
