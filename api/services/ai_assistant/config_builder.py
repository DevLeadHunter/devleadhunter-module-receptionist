"""Build a prospect's AI assistant configuration: brand accent, languages, persona.

The assistant wears the prospect's own visual identity (accent colour pulled from the logo, exactly
like the generated sites) and speaks the languages that matter in the prospect's country — a real
lever in Belgium and Luxembourg, where a business serves several language communities.
"""

import unicodedata
from typing import Any

from enums.ai_assistant_persona_gender import AiAssistantPersonaGender
from services.ai_assistant.masculine_first_names import MASCULINE_FIRST_NAMES
from services.brand_color_service import brand_color_service

DEFAULT_ASSISTANT_NAME = "Sofia"
DEFAULT_TONE = "chaleureux, professionnel et concis"
_FALLBACK_LANGUAGES = ["fr", "en"]

# Active languages offered per country. The assistant still detects and replies in the visitor's own
# language; this only bounds the offer shown up front. Luxembourg is included ahead of the sourcing
# pipeline supporting it (see country enum), because it is the module's primary target.
_LANGUAGES_BY_COUNTRY: dict[str, list[str]] = {
    "LU": ["fr", "de", "en", "lu"],
    "BE": ["fr", "nl", "en"],
    "CH": ["fr", "de", "en"],
    "FR": ["fr", "en"],
}


class AiAssistantConfigBuilder:
    """Resolves the accent colour, languages and persona defaults for a prospect's assistant."""

    def build_config(
        self,
        *,
        country: str | None = None,
        logo_url: str | None = None,
        assistant_name: str | None = None,
        languages: list[str] | None = None,
        tone: str | None = None,
        use_brand_color: bool = True,
    ) -> dict[str, Any]:
        """Resolve the assistant configuration for a prospect.

        Args:
            country: The prospect's ISO alpha-2 country code, driving the default languages.
            logo_url: The prospect's logo URL, used to pull the brand accent colour.
            assistant_name: An explicit persona name; falls back to the default.
            languages: Explicit active languages; falls back to the country defaults.
            tone: An explicit persona tone; falls back to the default.
            use_brand_color: When False, no accent is pulled and the widget keeps a neutral colour.

        Returns:
            The configuration dict (``assistant_name``, ``languages``, ``tone``, ``accent_color``).
        """
        resolved_languages = self._clean_languages(languages) or self._languages_for_country(country)
        accent = brand_color_service.extract_brand_color(logo_url) if use_brand_color else None
        return {
            "assistant_name": (assistant_name or "").strip() or DEFAULT_ASSISTANT_NAME,
            "languages": resolved_languages,
            "tone": (tone or "").strip() or DEFAULT_TONE,
            "accent_color": accent,
        }

    def resolve_persona_gender(self, assistant_name: str | None) -> AiAssistantPersonaGender:
        """Resolve the grammatical gender the persona speaks in, from its first name.

        Args:
            assistant_name: The persona name as configured (e.g. "Sofia", "Jean-Pierre").

        Returns:
            Masculine for a usual male first name, feminine otherwise (the default persona is feminine).
        """
        normalized = unicodedata.normalize("NFKD", assistant_name or "").encode("ascii", "ignore").decode("ascii")
        first_name = normalized.strip().lower().replace("-", " ").split(" ")[0]
        if first_name in MASCULINE_FIRST_NAMES:
            return AiAssistantPersonaGender.MASCULINE
        return AiAssistantPersonaGender.FEMININE

    def _languages_for_country(self, country: str | None) -> list[str]:
        code = (country or "").strip().upper()
        return list(_LANGUAGES_BY_COUNTRY.get(code, _FALLBACK_LANGUAGES))

    @staticmethod
    def _clean_languages(languages: list[str] | None) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for code in languages or []:
            if not isinstance(code, str):
                continue
            normalized = code.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                cleaned.append(normalized)
        return cleaned


ai_assistant_config_builder = AiAssistantConfigBuilder()
