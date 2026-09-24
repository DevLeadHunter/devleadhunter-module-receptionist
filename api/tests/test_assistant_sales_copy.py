"""
The assistant's sales copy: the 79 € default price, the prospecting templates and the demo page price.

Migrations run against an in-memory SQLite holding just the columns they touch.
"""

import asyncio
import importlib
import pkgutil
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import migrations.raise_assistant_default_price as price_migration
import migrations.rewrite_assistant_emails_missed_requests as emails_migration
import models
from core.config import settings
from core.database import Base
from models.prospect_db import ProspectDB
from seeders.email_template_seeder import EMAIL_TEMPLATE_LIBRARY
from services.ai_assistant.assistant_service import ai_assistant_service
from services.assistant_pricing_service import DEFAULT_MONTHLY_PRICE_CENTS, AssistantPricingService
from services.sms.gsm_segments import segment_count
from services.sms.templates import SMS_TEMPLATE_LIBRARY
from services.sms_service import sms_service

for _module in pkgutil.iter_modules(models.__path__):
    importlib.import_module("models." + _module.name)

_ASSISTANT_EMAILS = [
    template for template in EMAIL_TEMPLATE_LIBRARY if str(template["name"]).startswith("Assistant IA")
]
_ASSISTANT_SMS = [template for template in SMS_TEMPLATE_LIBRARY if template.key.startswith("assistant-")]


def _bare_engine(*ddl: str):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        for statement in ddl:
            conn.execute(text(statement))
        conn.commit()
    return engine


def test_the_default_assistant_price_is_79_euros() -> None:
    db = sessionmaker(bind=_bare_engine())()
    Base.metadata.create_all(db.get_bind())

    assert DEFAULT_MONTHLY_PRICE_CENTS == 7900
    assert AssistantPricingService.monthly_price_cents(db, 404) == 7900
    assert AssistantPricingService.annual_price_cents(db, 404) == 79000


def test_accounts_left_on_the_old_default_move_to_79_euros(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _bare_engine(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, assistant_monthly_price_cents INT)",
        "INSERT INTO users (id, email, assistant_monthly_price_cents) VALUES (1, 'a@x.fr', 2900), (2, 'b@x.fr', 4900)",
    )
    monkeypatch.setattr(price_migration, "engine", engine)

    price_migration.run_migration()
    price_migration.run_migration()

    with engine.connect() as conn:
        prices = conn.execute(text("SELECT id, assistant_monthly_price_cents FROM users ORDER BY id")).all()
    assert [tuple(row) for row in prices] == [(1, 7900), (2, 4900)]


def test_the_seeded_assistant_emails_are_rewritten_in_place(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _bare_engine(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)",
        "CREATE TABLE email_templates (id INTEGER PRIMARY KEY, user_id INT, name TEXT, subject TEXT, "
        "body_html TEXT, variables TEXT, is_active INT, category TEXT, sort_order INT)",
    )
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO users (id, email) VALUES (1, :email)"), {"email": settings.admin_email})
        for template_id, name in ((10, "Assistant IA - demandes captées"), (11, "Assistant IA - réponses 24/7")):
            conn.execute(
                text(
                    "INSERT INTO email_templates (id, user_id, name, subject, body_html, variables, is_active, "
                    "category, sort_order) VALUES (:id, 1, :name, 'Ancien', '<p>Ancien</p>', '[]', 1, 'first_email', 0)"
                ),
                {"id": template_id, "name": name},
            )
        conn.commit()
    monkeypatch.setattr(emails_migration, "engine", engine)

    emails_migration.run_migration()
    emails_migration.run_migration()

    with engine.connect() as conn:
        rows = {
            row[0]: tuple(row[1:])
            for row in conn.execute(text("SELECT id, name, subject, sort_order FROM email_templates"))
        }
    assert rows[10] == ("Assistant IA - devis par photo", "Une photo, un devis demandé", 11)
    assert rows[11] == ("Assistant IA - réponses 24/7", "Vos clients écrivent le soir, personne ne répond", 10)


def test_an_old_photo_template_is_archived_when_the_new_one_already_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _bare_engine(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)",
        "CREATE TABLE email_templates (id INTEGER PRIMARY KEY, user_id INT, name TEXT, subject TEXT, "
        "body_html TEXT, variables TEXT, is_active INT, category TEXT, sort_order INT)",
    )
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO users (id, email) VALUES (1, :email)"), {"email": settings.admin_email})
        for template_id, name in ((10, "Assistant IA - demandes captées"), (12, "Assistant IA - devis par photo")):
            conn.execute(
                text(
                    "INSERT INTO email_templates (id, user_id, name, subject, body_html, variables, is_active, "
                    "category, sort_order) VALUES (:id, 1, :name, 'x', '<p>x</p>', '[]', 1, 'first_email', 0)"
                ),
                {"id": template_id, "name": name},
            )
        conn.commit()
    monkeypatch.setattr(emails_migration, "engine", engine)

    emails_migration.run_migration()

    with engine.connect() as conn:
        rows = {
            row[0]: (row[1], row[2]) for row in conn.execute(text("SELECT id, name, is_active FROM email_templates"))
        }
    assert rows[10] == ("Assistant IA - demandes captées", 0)
    assert rows[12] == ("Assistant IA - devis par photo", 1)


def test_every_assistant_email_links_the_demo_once_and_states_the_price() -> None:
    assert len(_ASSISTANT_EMAILS) == 5
    for template in _ASSISTANT_EMAILS:
        body = str(template["body_html"])
        assert body.count("{lien_assistant}") == 1, template["name"]
        assert "{prix_assistant}" in body, template["name"]
        assert "—" not in body + str(template["subject"]), template["name"]
        assert "http" not in body, template["name"]


def test_every_assistant_sms_links_the_demo_once_without_a_scheme() -> None:
    assert len(_ASSISTANT_SMS) == 5
    for template in _ASSISTANT_SMS:
        assert template.body.count("{lien_assistant}") == 1, template.key
        assert "http" not in template.body, template.key


def test_every_assistant_sms_fits_one_segment_with_a_45_character_link() -> None:
    variables = {
        "salutation": "Bonjour Geoffrey",
        "lien_assistant": "demo.dibodev.fr/ia/plomberie-chauffage-dupont",
        "prix_assistant": "79 €",
        "signature": "Léo",
    }
    assert len(variables["lien_assistant"]) == 45
    for template in _ASSISTANT_SMS:
        body = sms_service.compose_from_template(template, variables)
        assert segment_count(body) == 1, f"{template.key}: {len(body)} chars"


def test_a_demo_page_shows_the_price_and_a_sold_assistant_does_not() -> None:
    from api.v1.routes.ai_assistant_widget import get_public_assistant

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db: Session = sessionmaker(bind=engine)()
    prospect = ProspectDB(name="Garage Martin", category="Garagiste", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Garage Martin", prospect_id=prospect.id, country="FR", use_brand_color=False
    )

    demo = asyncio.run(get_public_assistant(assistant.slug, db))
    assistant.status = "delivered"
    db.commit()
    sold = asyncio.run(get_public_assistant(assistant.slug, db))

    assert demo.monthly_price_label == "79 €"
    assert sold.monthly_price_label is None


def test_a_demo_page_estimates_the_closed_hours_from_the_google_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.v1.routes.ai_assistant_widget as routes
    from services.ai_assistant.opening_hours import OpeningHoursCalendar

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db: Session = sessionmaker(bind=engine)()
    prospect = ProspectDB(name="Garage Martin", category="Garage automobile", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Garage Martin", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    weekdays = ("lundi", "mardi", "mercredi", "jeudi", "vendredi")
    assistant.knowledge_json = {
        **assistant.knowledge_json,
        "opening_hours": [{"day": day, "hours": "08:00–12:00, 14:00–18:00"} for day in weekdays]
        + [{"day": "samedi", "hours": "Fermé"}, {"day": "dimanche", "hours": "Fermé"}],
    }
    db.commit()
    monkeypatch.setattr(
        OpeningHoursCalendar, "business_now", staticmethod(lambda: datetime(2026, 9, 24, 10, 0, tzinfo=UTC))
    )

    demo = asyncio.run(routes.get_public_assistant(assistant.slug, db))
    assistant.status = "delivered"
    db.commit()
    sold = asyncio.run(routes.get_public_assistant(assistant.slug, db))
    assistant.status = "active"
    assistant.knowledge_json = {
        **assistant.knowledge_json,
        "opening_hours": [{"day": day, "hours": "Fermé"} for day in (*weekdays, "samedi", "dimanche")],
    }
    db.commit()
    never_open = asyncio.run(routes.get_public_assistant(assistant.slug, db))

    assert demo.closed_hours is not None
    # 40 h open a week; from 7:00 to 22:00, closed 65 h of 105 (62 %), 274 h in September 2026; a garage's base
    # of 30 requests a month × 62 % ≈ 19.
    assert demo.closed_hours.model_dump() == {
        "open_hours_per_week": 40,
        "closed_share_pct": 62,
        "closed_hours_in_month": 274,
        "month": 9,
        "trade_label": "un garage",
        "monthly_requests": 30,
        "estimated_requests": 19,
    }
    assert sold.closed_hours is None
    assert never_open.closed_hours is None  # A listing closed every day says nothing useful.


@pytest.mark.parametrize(
    ("category", "label"),
    [
        ("Plombier chauffagiste", "un plombier"),
        ("Garage automobile", "un garage"),
        ("Kinésithérapeute", "un cabinet de santé"),
        ("Esthéticienne", "un institut de beauté"),
        ("Barbier", "un salon de coiffure"),
        ("Restaurant barbecue", "un restaurant"),
        ("Installateur de portes de garage", "une entreprise du bâtiment"),
        ("Institut de formation", "un commerce comme le vôtre"),
        ("Espace vert", "un commerce comme le vôtre"),
        (None, "un commerce comme le vôtre"),
    ],
)
def test_the_request_volume_follows_the_trade_by_word_start(category: str | None, label: str) -> None:
    from services.ai_assistant.request_volume import AiAssistantRequestVolume

    assert AiAssistantRequestVolume.for_category(category).label == label


def test_the_estimate_rounds_half_up_as_a_reader_does() -> None:
    from services.ai_assistant.request_volume import AiAssistantRequestVolume

    assert AiAssistantRequestVolume.estimate(25, 50) == 13  # 12.5, where round() would say 12
    assert AiAssistantRequestVolume.estimate(30, 62) == 19
    assert AiAssistantRequestVolume.estimate(20, 7) == 1


def test_an_assistant_without_a_prospect_is_estimated_on_the_default_base(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.v1.routes.ai_assistant_widget as routes
    from services.ai_assistant.opening_hours import OpeningHoursCalendar

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db: Session = sessionmaker(bind=engine)()
    days = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
    assistant = ai_assistant_service.create(
        db,
        user_id=7,
        business_name="Cabinet Meyer",
        country="FR",
        use_brand_color=False,
        enrichment={"opening_hours": [{"day": day, "hours": "09:00–17:00"} for day in days]},
    )
    monkeypatch.setattr(
        OpeningHoursCalendar, "business_now", staticmethod(lambda: datetime(2026, 9, 24, 10, 0, tzinfo=UTC))
    )

    demo = asyncio.run(routes.get_public_assistant(assistant.slug, db))

    # Open 8 h a day: from 7:00 to 22:00, closed 7 h of 15 (47 %); 20 requests × 47 % ≈ 9.
    assert demo.closed_hours is not None
    assert (
        demo.closed_hours.trade_label,
        demo.closed_hours.closed_share_pct,
        demo.closed_hours.estimated_requests,
    ) == (
        "un commerce comme le vôtre",
        47,
        9,
    )
