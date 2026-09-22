"""Tests for the AI assistant knowledge base and system prompt builder."""

from services.ai_assistant.knowledge_builder import ai_assistant_knowledge_builder

_ENRICHMENT = {
    "logo_url": "https://cdn/logo.png",
    "rating": 4.9,
    "reviews_count": 128,
    "description": "  Agence   immobilière  de référence.  ",
    "reviews": [
        {"text": "Super accompagnement ! … Plus", "author": "Marie D.", "rating": 5},
        {"text": "   ", "author": "Vide"},
        {"not_a_dict": True},
    ],
    "opening_hours": [
        {"day": "lundi", "hours": "09:00–18:30"},
        {"day": "samedi (Assomption)", "hours": "10:00–16:00"},
        {"day": "Note", "hours": "Les horaires peuvent varier"},
    ],
    "services": ["Vente", "vente", "  Location  ", 123, "Estimation"],
    "social_links": {"facebook": "https://fb.example", "instagram": ""},
}


def test_build_knowledge_shapes_and_cleans_enrichment() -> None:
    """build_knowledge maps every enrichment field, cleaning and de-duplicating along the way."""
    kb = ai_assistant_knowledge_builder.build_knowledge(
        business_name="LUMA Immobilier",
        city="Luxembourg",
        address="12 Avenue de la Liberté",
        phone="+352 27 86 41 20",
        email="bonjour@luma-immo.lu",
        enrichment=_ENRICHMENT,
    )

    assert kb["identity"]["business_name"] == "LUMA Immobilier"
    assert kb["identity"]["city"] == "Luxembourg"
    assert kb["identity"]["description"] == "Agence immobilière de référence."
    assert kb["rating"] == {"value": "4,9/5", "count": "128"}

    days = [row["day"] for row in kb["opening_hours"]]
    assert "lundi" in days and "samedi" in days
    assert "Note" not in days

    assert kb["services"] == ["Vente", "Location", "Estimation"]

    assert len(kb["reviews"]) == 1
    assert "… Plus" not in kb["reviews"][0]["text"]
    assert kb["reviews"][0]["author"] == "Marie D."

    assert kb["social"] == {"facebook": "https://fb.example"}


def test_build_knowledge_without_enrichment_is_safe() -> None:
    """Without enrichment the knowledge base is minimal but never crashes."""
    kb = ai_assistant_knowledge_builder.build_knowledge(business_name="Cabinet Meyer", enrichment=None)

    assert kb["identity"]["business_name"] == "Cabinet Meyer"
    assert kb["rating"] is None
    assert kb["services"] == []
    assert kb["reviews"] == []
    assert kb["opening_hours"] == []


def test_render_system_prompt_grounds_on_knowledge() -> None:
    """The system prompt names the persona, states the grounding rule and injects the real data."""
    kb = ai_assistant_knowledge_builder.build_knowledge(
        business_name="LUMA Immobilier", city="Luxembourg", enrichment=_ENRICHMENT
    )
    prompt = ai_assistant_knowledge_builder.render_system_prompt(
        kb, assistant_name="Sofia", languages=["fr", "en", "de"], tone="chaleureux et direct"
    )

    assert "Sofia" in prompt
    assert "LUMA Immobilier" in prompt
    assert "N'invente jamais" in prompt
    assert "français, anglais, allemand" in prompt
    assert "4,9/5" in prompt
    assert "Vente" in prompt
    assert "chaleureux et direct" in prompt


def test_render_system_prompt_flags_missing_hours() -> None:
    """With no opening hours the prompt tells the assistant to offer a callback instead of inventing them."""
    kb = ai_assistant_knowledge_builder.build_knowledge(business_name="Cabinet Meyer", enrichment=None)
    prompt = ai_assistant_knowledge_builder.render_system_prompt(kb, assistant_name="Léa")

    assert "non communiqués" in prompt
