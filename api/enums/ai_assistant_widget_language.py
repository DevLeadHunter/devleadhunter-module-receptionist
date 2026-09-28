"""Languages the assistant widget speaks up front: the single list the widget, the dashboard and the API share."""

from __future__ import annotations

from enum import Enum

# Codes read as another widget language: « lu » named Luxembourgish before the widget moved to BCP 47's « lb ».
_ALIASES: dict[str, str] = {"lu": "lb"}


class AiAssistantWidgetLanguage(str, Enum):
    """A language the widget offers greetings and suggestions in (the model still replies in any language)."""

    FR = "fr"
    NL = "nl"
    EN = "en"
    DE = "de"
    LB = "lb"

    @classmethod
    def from_code(cls, code: str | None) -> AiAssistantWidgetLanguage | None:
        """
        The widget language a code names, whatever its case, region or legacy spelling.

        Args:
            code: A language code as stored or sent (« lb », « LB », « lb-LU », the legacy « lu »).

        Returns:
            The widget language, or None when the widget does not speak it.
        """
        primary = (code or "").strip().lower().replace("_", "-").split("-", 1)[0]
        primary = _ALIASES.get(primary, primary)
        return next((language for language in cls if language.value == primary), None)

    @classmethod
    def normalize_codes(cls, codes: list[str] | None) -> list[str]:
        """
        The widget languages a list of codes names, legacy spellings read, the others dropped, each once.

        Args:
            codes: Language codes as stored or sent.

        Returns:
            Their widget-language codes, in their first order.
        """
        normalized: list[str] = []
        for code in codes or []:
            language = cls.from_code(code)
            if language is not None and language.value not in normalized:
                normalized.append(language.value)
        return normalized

    @classmethod
    def _missing_(cls, value: object) -> AiAssistantWidgetLanguage | None:
        """Read a differently spelled code (« LB », « lu ») as the language it names when a model parses it."""
        return cls.from_code(value) if isinstance(value, str) else None
