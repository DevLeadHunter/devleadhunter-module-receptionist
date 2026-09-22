"""Tests for the AI assistant generation and public lookup service."""

import importlib
import pkgutil

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


def test_get_public_by_slug_returns_active_only(db) -> None:
    """The public lookup returns an active assistant and never an unknown or inactive one."""
    created = ai_assistant_service.create(
        db, user_id=1, business_name="Cabinet Meyer", country="FR", use_brand_color=False
    )
    assert ai_assistant_service.get_public_by_slug(db, created.slug) is not None
    assert ai_assistant_service.get_public_by_slug(db, "inexistant") is None

    created.status = "expired"
    db.commit()
    assert ai_assistant_service.get_public_by_slug(db, created.slug) is None
