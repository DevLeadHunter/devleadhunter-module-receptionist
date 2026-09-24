"""Tests for the AI assistant generation and public lookup service."""

import importlib
import pkgutil
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from core.database import Base
from services.ai_assistant.assistant_service import ai_assistant_service

# Load every model so SQLAlchemy can configure the mappers (relationships resolve across models).
for _module in pkgutil.iter_modules(models.__path__):
    importlib.import_module("models." + _module.name)

_ENRICHMENT = {
    "logo_url": None,
    "rating": 4.8,
    "reviews_count": 96,
    "description": "Agence de référence.",
    "services": ["Vente", "Location"],
    "opening_hours": [],
    "reviews": [],
    "social_links": {},
}


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_build_fields_assembles_knowledge_and_persona() -> None:
    """build_fields folds the config accent into the knowledge palette and resolves the persona."""
    fields = ai_assistant_service.build_fields(
        business_name="LUMA Immobilier",
        city="Luxembourg",
        country="LU",
        enrichment=_ENRICHMENT,
        use_brand_color=False,
    )
    assert fields["assistant_name"] == "Sofia"
    assert fields["languages"] == ["fr", "de", "en", "lu"]
    assert fields["knowledge_json"]["palette"] == {"accent": None}
    assert fields["knowledge_json"]["identity"]["business_name"] == "LUMA Immobilier"
    assert fields["description"] == "Agence de référence."


def test_create_persists_active_assistant_with_unique_slug(db) -> None:
    """Two assistants for the same business get distinct slugs, both active."""
    first = ai_assistant_service.create(
        db, user_id=1, business_name="LUMA Immobilier", country="LU", enrichment=_ENRICHMENT, use_brand_color=False
    )
    second = ai_assistant_service.create(
        db, user_id=1, business_name="LUMA Immobilier", country="LU", enrichment=_ENRICHMENT, use_brand_color=False
    )
    assert first.slug == "luma-immobilier"
    assert second.slug == "luma-immobilier-2"
    assert first.status == "active"


def test_get_public_by_slug_returns_active_or_delivered_only(db) -> None:
    """The public lookup serves a demo and a sold assistant, never an unknown, expired or deleted one."""
    created = ai_assistant_service.create(
        db, user_id=1, business_name="Cabinet Meyer", country="FR", use_brand_color=False
    )
    assert ai_assistant_service.get_public_by_slug(db, created.slug) is not None
    assert ai_assistant_service.get_public_by_slug(db, "inexistant") is None

    created.status = "delivered"
    db.commit()
    assert ai_assistant_service.get_public_by_slug(db, created.slug) is not None

    created.status = "expired"
    db.commit()
    assert ai_assistant_service.get_public_by_slug(db, created.slug) is None

    created.status = "delivered"
    created.deleted_at = datetime.utcnow()
    db.commit()
    assert ai_assistant_service.get_public_by_slug(db, created.slug) is None


def test_get_active_for_prospect_scopes_to_the_user_and_the_demo(db) -> None:
    """Prospection links only the sender's own active demo: another member's, a sold or a deleted one never leak."""
    mine = ai_assistant_service.create(
        db, user_id=1, business_name="Cabinet Meyer", prospect_id=42, country="FR", use_brand_color=False
    )
    ai_assistant_service.create(
        db, user_id=2, business_name="Cabinet Meyer", prospect_id=42, country="FR", use_brand_color=False
    )
    found = ai_assistant_service.get_active_for_prospect(db, prospect_id=42, user_id=1)
    assert found is not None and found.id == mine.id
    assert ai_assistant_service.get_active_for_prospect(db, prospect_id=42, user_id=3) is None

    mine.status = "delivered"
    db.commit()
    assert ai_assistant_service.get_active_for_prospect(db, prospect_id=42, user_id=1) is None

    mine.status = "active"
    mine.deleted_at = datetime.utcnow()
    db.commit()
    assert ai_assistant_service.get_active_for_prospect(db, prospect_id=42, user_id=1) is None


def test_update_edits_persona_languages_and_accent(db) -> None:
    """update applies only the provided fields and reassigns the palette accent."""
    assistant = ai_assistant_service.create(
        db, user_id=1, business_name="LUMA Immobilier", country="LU", use_brand_color=False
    )
    updated = ai_assistant_service.update(
        db,
        assistant,
        {"assistant_name": "Marc", "languages": ["fr", "en"], "tone": "direct", "accent_color": "#1e6fd8"},
    )
    assert updated.assistant_name == "Marc"
    assert updated.languages == ["fr", "en"]
    assert updated.tone == "direct"
    assert updated.knowledge_json["palette"]["accent"] == "#1e6fd8"
    # A field left out of the payload stays untouched.
    assert updated.business_name == "LUMA Immobilier"


def test_update_empty_accent_clears_to_neutral(db) -> None:
    """An empty accent clears the widget colour back to neutral (None)."""
    assistant = ai_assistant_service.create(db, user_id=1, business_name="X", country="FR")
    updated = ai_assistant_service.update(db, assistant, {"accent_color": ""})
    assert updated.knowledge_json["palette"]["accent"] is None


def test_update_blank_name_keeps_previous(db) -> None:
    """A blank assistant_name keeps the current persona rather than wiping it."""
    assistant = ai_assistant_service.create(db, user_id=1, business_name="X", country="FR")
    before = assistant.assistant_name
    updated = ai_assistant_service.update(db, assistant, {"assistant_name": "   "})
    assert updated.assistant_name == before


def test_regenerate_refreshes_knowledge_but_keeps_branding_and_slug(db) -> None:
    """Regenerate rebuilds grounding + contact from the prospect, preserving look, voice and slug."""
    assistant = ai_assistant_service.create(
        db,
        user_id=1,
        business_name="LUMA Immobilier",
        prospect_id=42,
        country="LU",
        enrichment=_ENRICHMENT,
        use_brand_color=False,
    )
    ai_assistant_service.update(
        db,
        assistant,
        {"assistant_name": "Marc", "tone": "direct", "languages": ["fr", "de"], "accent_color": "#1e6fd8"},
    )
    original_slug = assistant.slug

    prospect = SimpleNamespace(
        city="Esch-sur-Alzette",
        address="2 rue Neuve",
        phone="+352 27 00 00 00",
        email="hello@luma.lu",
        country="LU",
    )
    refreshed_enrichment = {**_ENRICHMENT, "description": "Nouvelle description à jour."}
    updated = ai_assistant_service.regenerate(
        db, assistant=assistant, prospect=prospect, enrichment=refreshed_enrichment
    )

    # Grounding + contact refreshed from the prospect's latest data.
    assert updated.description == "Nouvelle description à jour."
    assert updated.knowledge_json["identity"]["description"] == "Nouvelle description à jour."
    assert updated.phone == "+352 27 00 00 00"
    assert updated.city == "Esch-sur-Alzette"
    # Branding, persona and public slug all preserved.
    assert updated.assistant_name == "Marc"
    assert updated.tone == "direct"
    assert updated.languages == ["fr", "de"]
    assert updated.knowledge_json["palette"]["accent"] == "#1e6fd8"
    assert updated.business_name == "LUMA Immobilier"
    assert updated.slug == original_slug
