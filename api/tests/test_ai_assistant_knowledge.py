"""Tests for the AI assistant knowledge base and system prompt builder."""

from datetime import datetime

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
    assert "N'invente JAMAIS" in prompt
    assert "français, anglais, allemand" in prompt
    assert "4,9/5" in prompt
    assert "Vente" in prompt
    assert "chaleureux et direct" in prompt


def test_render_system_prompt_flags_missing_hours() -> None:
    """With no opening hours the prompt tells the assistant to offer a callback instead of inventing them."""
    kb = ai_assistant_knowledge_builder.build_knowledge(business_name="Cabinet Meyer", enrichment=None)
    prompt = ai_assistant_knowledge_builder.render_system_prompt(kb, assistant_name="Léa")

    assert "non communiqués" in prompt


def test_render_system_prompt_states_the_business_date_and_time() -> None:
    """The prompt carries the current local date and time, tied to the hours, so « ouvert aujourd'hui ? » is answered."""
    kb = ai_assistant_knowledge_builder.build_knowledge(business_name="Cabinet Meyer", enrichment=_ENRICHMENT)
    prompt = ai_assistant_knowledge_builder.render_system_prompt(
        kb, assistant_name="Sofia", now=datetime(2026, 9, 24, 14, 5)
    )

    assert "AUJOURD'HUI : jeudi 24 septembre 2026, il est 14:05" in prompt
    assert prompt.index("AUJOURD'HUI") < prompt.index("HORAIRES :")


def test_render_system_prompt_defaults_to_the_current_date() -> None:
    """Without an explicit clock the prompt still states today's date."""
    kb = ai_assistant_knowledge_builder.build_knowledge(business_name="Cabinet Meyer", enrichment=None)
    prompt = ai_assistant_knowledge_builder.render_system_prompt(kb, assistant_name="Sofia")

    assert "AUJOURD'HUI : " in prompt
    assert str(datetime.now().year) in prompt


def test_render_system_prompt_forbids_implying_absent_services() -> None:
    """The assistant may not commit the business to a service the knowledge base does not list."""
    kb = ai_assistant_knowledge_builder.build_knowledge(business_name="Tasty Korea", enrichment=None)
    prompt = ai_assistant_knowledge_builder.render_system_prompt(kb, assistant_name="Sofia")

    assert "Ne laisse JAMAIS entendre qu'un service absent" in prompt
    assert "livraison" in prompt
    assert "tu ne t'engages à rien à la place de l'entreprise" in prompt


def test_render_system_prompt_agrees_with_the_persona_gender() -> None:
    """The persona's wording follows its first name: feminine for Sofia, masculine for Marc."""
    kb = ai_assistant_knowledge_builder.build_knowledge(business_name="Cabinet Meyer", enrichment=None)
    sofia = ai_assistant_knowledge_builder.render_system_prompt(kb, assistant_name="Sofia")
    marc = ai_assistant_knowledge_builder.render_system_prompt(kb, assistant_name="Marc")

    assert "Tu es Sofia, l'assistante virtuelle de Cabinet Meyer" in sofia
    assert "Tu parles de toi au féminin" in sofia
    assert "chaleureuse, humaine et confiante" in sofia
    assert "Tu es Marc, l'assistant virtuel de Cabinet Meyer" in marc
    assert "Tu parles de toi au masculin" in marc
    assert "chaleureux, humain et confiant" in marc
