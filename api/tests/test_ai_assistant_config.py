"""Tests for the AI assistant configuration builder."""

from enums.ai_assistant_persona_gender import AiAssistantPersonaGender
from services.ai_assistant import config_builder as config_module
from services.ai_assistant.config_builder import (
    DEFAULT_ASSISTANT_NAME,
    DEFAULT_TONE,
    ai_assistant_config_builder,
)


def test_languages_follow_the_country() -> None:
    """Each targeted country offers its own language mix; an unknown country falls back to FR/EN."""
    assert ai_assistant_config_builder.build_config(country="LU")["languages"] == ["fr", "de", "en", "lu"]
    assert ai_assistant_config_builder.build_config(country="be")["languages"] == ["fr", "nl", "en"]
    assert ai_assistant_config_builder.build_config(country="CH")["languages"] == ["fr", "de", "en"]
    assert ai_assistant_config_builder.build_config(country="US")["languages"] == ["fr", "en"]


def test_explicit_values_win_and_are_cleaned() -> None:
    """Explicit persona and languages override the defaults; languages are lowercased and de-duplicated."""
    config = ai_assistant_config_builder.build_config(
        country="FR",
        assistant_name="  Léa  ",
        languages=["FR", "fr", "EN"],
        tone="  direct  ",
        use_brand_color=False,
    )
    assert config["assistant_name"] == "Léa"
    assert config["languages"] == ["fr", "en"]
    assert config["tone"] == "direct"
    assert config["accent_color"] is None


def test_defaults_when_nothing_provided() -> None:
    """With no persona given, the default name and tone are used."""
    config = ai_assistant_config_builder.build_config(country="FR", use_brand_color=False)
    assert config["assistant_name"] == DEFAULT_ASSISTANT_NAME
    assert config["tone"] == DEFAULT_TONE


def test_resolve_persona_gender_follows_the_first_name() -> None:
    """A usual male first name speaks in the masculine; any other name (the default Sofia included) in the feminine."""
    assert ai_assistant_config_builder.resolve_persona_gender("Sofia") is AiAssistantPersonaGender.FEMININE
    assert ai_assistant_config_builder.resolve_persona_gender("Marc") is AiAssistantPersonaGender.MASCULINE
    assert ai_assistant_config_builder.resolve_persona_gender("  LÉO ") is AiAssistantPersonaGender.MASCULINE
    assert ai_assistant_config_builder.resolve_persona_gender("Jean-Pierre") is AiAssistantPersonaGender.MASCULINE
    assert ai_assistant_config_builder.resolve_persona_gender("") is AiAssistantPersonaGender.FEMININE
    assert ai_assistant_config_builder.resolve_persona_gender(None) is AiAssistantPersonaGender.FEMININE


def test_brand_color_pulled_from_logo(monkeypatch) -> None:
    """The accent colour comes from the logo when brand colouring is on, and is skipped when off."""
    monkeypatch.setattr(
        config_module.brand_color_service, "extract_brand_color", lambda url: "#1f5c47" if url else None
    )
    on = ai_assistant_config_builder.build_config(country="LU", logo_url="https://cdn/logo.png")
    off = ai_assistant_config_builder.build_config(country="LU", logo_url="https://cdn/logo.png", use_brand_color=False)
    assert on["accent_color"] == "#1f5c47"
    assert off["accent_color"] is None
