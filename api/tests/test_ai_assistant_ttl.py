"""The assistant demo countdown starts at the first email or SMS carrying its link; only demos expire."""

import importlib
import pkgutil
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import models
from core.config import settings
from core.database import Base
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from services.ai_assistant.assistant_service import ai_assistant_service

# Load every model so SQLAlchemy can configure the mappers (relationships resolve across models).
for _module in pkgutil.iter_modules(models.__path__):
    importlib.import_module("models." + _module.name)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _assistant(db: Session, *, user_id: int = 1, prospect_id: int = 42) -> AiAssistant:
    return ai_assistant_service.create(
        db, user_id=user_id, business_name="Cabinet Meyer", prospect_id=prospect_id, country="FR", use_brand_color=False
    )


def test_start_demo_ttl_sets_the_expiry_from_the_send_date(db) -> None:
    """The first send stamps the send date and an expiry TTL days later; a later send changes nothing."""
    assistant = _assistant(db)
    sent_at = datetime(2026, 9, 24, 10, 0)

    assert ai_assistant_service.start_demo_ttl(db, assistant, sent_at) is True
    assert assistant.demo_link_sent_at.replace(tzinfo=None) == sent_at
    assert assistant.expires_at.replace(tzinfo=None) == sent_at + timedelta(days=settings.demo_site_ttl_days)

    assert ai_assistant_service.start_demo_ttl(db, assistant, sent_at + timedelta(days=3)) is False
    assert assistant.demo_link_sent_at.replace(tzinfo=None) == sent_at


def test_start_demo_ttl_never_touches_a_sold_assistant(db) -> None:
    """A delivered assistant is the client's production widget: it never counts down."""
    assistant = _assistant(db)
    assistant.status = AiAssistantStatus.DELIVERED.value
    db.commit()

    assert ai_assistant_service.start_demo_ttl(db, assistant, datetime.now(UTC)) is False
    assert assistant.expires_at is None


def test_maybe_start_ttl_after_demo_email_needs_the_link_in_the_body(db) -> None:
    """Only an email that really carries the assistant link starts its countdown."""
    assistant = _assistant(db)
    sent_at = datetime(2026, 9, 24, 12, 0)

    ai_assistant_service.maybe_start_ttl_after_demo_email(
        db, user_id=1, prospect_id=42, sent_at=sent_at, body_html="<p>Sans lien</p>"
    )
    assert assistant.demo_link_sent_at is None

    body = f'<a href="https://demo.dibodev.fr/ia/{assistant.slug}?src=email">Essayer</a>'
    ai_assistant_service.maybe_start_ttl_after_demo_email(
        db, user_id=1, prospect_id=42, sent_at=sent_at, body_html=body
    )
    assert assistant.demo_link_sent_at is not None
    assert assistant.expires_at is not None


def test_maybe_start_ttl_ignores_another_users_assistant(db) -> None:
    """On a shared prospect, another member's send never starts my assistant's countdown."""
    assistant = _assistant(db, user_id=2)

    ai_assistant_service.maybe_start_ttl_after_demo_email(
        db, user_id=1, prospect_id=42, sent_at=datetime(2026, 9, 24, 12, 0), body_html=f"/ia/{assistant.slug}"
    )
    assert assistant.demo_link_sent_at is None


def test_expire_due_assistants_expires_only_started_demos(db) -> None:
    """Past their countdown, demos expire and go dark; a sold, an unsent and a fresh assistant stay."""
    now = datetime.now(UTC)
    due = _assistant(db, prospect_id=1)
    ai_assistant_service.start_demo_ttl(db, due, now - timedelta(days=settings.demo_site_ttl_days + 1))
    sold = _assistant(db, prospect_id=2)
    ai_assistant_service.start_demo_ttl(db, sold, now - timedelta(days=60))
    sold.status = AiAssistantStatus.DELIVERED.value
    db.commit()
    unsent = _assistant(db, prospect_id=3)
    fresh = _assistant(db, prospect_id=4)
    ai_assistant_service.start_demo_ttl(db, fresh, now)

    assert ai_assistant_service.expire_due_assistants(db) == 1
    assert due.status == AiAssistantStatus.EXPIRED.value
    assert sold.status == AiAssistantStatus.DELIVERED.value
    assert unsent.status == AiAssistantStatus.ACTIVE.value
    assert fresh.status == AiAssistantStatus.ACTIVE.value
    assert ai_assistant_service.get_public_by_slug(db, due.slug) is None
    assert ai_assistant_service.expire_due_assistants(db) == 0
