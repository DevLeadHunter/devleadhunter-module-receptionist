"""The receptionist's cold emails: frank like the website's, plainly an AI, and renamed in place by the cut-over.

The library-wide copy rules of the core (``test_frank_email_template_library.py``) cover the website templates only:
the receptionist's templates are held to the same rules here, on top of their own.
"""

from __future__ import annotations

import re
from typing import NamedTuple

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from core.config import settings
from devleadhunter_receptionist.email_templates import RECEPTIONIST_EMAIL_TEMPLATES
from enums.email_template_category import EmailTemplateCategory
from migrations.reseed_frank_email_template_library import FrankEmailTemplateLibraryReseed
from models.campaign import Campaign, CampaignStatus
from models.email_template import EmailTemplate
from models.user import User
from seeders.email_template_seeder import full_email_template_library

_FORBIDDEN_WORDS = re.compile(r"\b(voici|cliquez|ici)\b", re.IGNORECASE)
_LONG_DASHES = ("—", "–")
_BIG_BRANDS = ("google", "apple", "facebook", "instagram")
_EXIT_MARKERS = ("non", "rien à faire")
_CLOSING_MARKERS = (*_EXIT_MARKERS, "Prenez votre temps")
_SINGLE_DOOR_RECEPTIONIST_EMAILS = ("Réceptionniste IA - franc", "Réceptionniste IA - en bref")
_GENDERED_RECEPTIONIST_WORDS = re.compile(
    r"\b(il|elle|virtuel|virtuelle|préparée|une réceptionniste|un réceptionniste|la réceptionniste)\b", re.IGNORECASE
)
_VARIABLE = re.compile(r"\{[a-z_]+\}")


class TestEmailLibraryShape:
    def test_names_are_unique_across_the_shared_library(self) -> None:
        names = [str(template["name"]) for template in full_email_template_library()]
        assert len(names) == len(set(names))

    def test_the_frank_website_templates_stay_pinned_first(self) -> None:
        library = full_email_template_library()
        by_name = {str(template["name"]): template for template in library}
        first_emails = [t for t in library if t["category"] == EmailTemplateCategory.FIRST_EMAIL.value]
        follow_ups = [t for t in library if t["category"] == EmailTemplateCategory.FOLLOW_UP.value]
        assert by_name["Franc - premier contact"]["sort_order"] == max(int(t["sort_order"]) for t in first_emails)  # type: ignore[call-overload]
        assert by_name["Franc - relance"]["sort_order"] == max(int(t["sort_order"]) for t in follow_ups)  # type: ignore[call-overload]

    def test_the_old_assistant_names_are_gone(self) -> None:
        assert not any(str(template["name"]).startswith("Assistant IA") for template in RECEPTIONIST_EMAIL_TEMPLATES)


class TestEmailCopyRules:
    def test_plain_words_everywhere(self) -> None:
        for template in RECEPTIONIST_EMAIL_TEMPLATES:
            copy = f"{template['subject']} {template['body_html']}"
            assert not any(dash in copy for dash in _LONG_DASHES), template["name"]
            assert _FORBIDDEN_WORDS.search(copy) is None, template["name"]
            assert "http" not in copy, template["name"]

    def test_subjects_are_short_lower_case_and_brand_free(self) -> None:
        for template in RECEPTIONIST_EMAIL_TEMPLATES:
            subject = str(template["subject"])
            assert subject[0].islower() or subject.startswith("{"), subject
            assert len(subject) <= 60, subject
            assert not any(brand in subject.lower() for brand in _BIG_BRANDS), subject

    def test_bodies_end_nude_so_the_signature_block_is_not_doubled(self) -> None:
        for template in RECEPTIONIST_EMAIL_TEMPLATES:
            body = str(template["body_html"])
            assert "{signature}" not in body, template["name"]
            assert body.endswith("</p>"), template["name"]
            last_paragraph = body.rsplit("<p>", 1)[1]
            assert any(marker in last_paragraph for marker in _CLOSING_MARKERS), template["name"]

    def test_no_follow_up_promises_to_be_the_last_message_nor_begs_for_a_no(self) -> None:
        for template in RECEPTIONIST_EMAIL_TEMPLATES:
            body = str(template["body_html"])
            assert "Dernier message" not in body and "promis" not in body, template["name"]
            assert "non merci" not in body and "Je range mes démos" not in body, template["name"]


class TestReceptionistEmailCopyRules:
    def test_eight_receptionist_emails_named_after_the_product(self) -> None:
        assert len(RECEPTIONIST_EMAIL_TEMPLATES) == 8
        for template in RECEPTIONIST_EMAIL_TEMPLATES:
            assert str(template["name"]).startswith("Réceptionniste IA - "), template["name"]

    def test_she_is_plainly_an_ai_with_her_own_address_and_a_refundable_first_month(self) -> None:
        for template in RECEPTIONIST_EMAIL_TEMPLATES:
            body = str(template["body_html"])
            assert "{assistant_virtuel}" in body and "IA" in body, template["name"]
            assert "pas une personne" not in body, template["name"]
            assert "{prix_assistant}" in body and "{prix}" not in body and "{prix_carte}" not in body, template["name"]
            assert "satisfait ou remboursé" in body, template["name"]
            assert "{date_expiration}" in body, template["name"]
            assert any(marker in body for marker in _EXIT_MARKERS), template["name"]

    def test_the_gendered_words_come_from_the_variables(self) -> None:
        for template in RECEPTIONIST_EMAIL_TEMPLATES:
            copy = _VARIABLE.sub("", f"{template['subject']} {template['body_html']}")
            assert _GENDERED_RECEPTIONIST_WORDS.search(copy) is None, template["name"]

    def test_she_never_assumes_the_prospect_has_a_website(self) -> None:
        for template in RECEPTIONIST_EMAIL_TEMPLATES:
            body = str(template["body_html"]).lower()
            assert "votre site" not in body, template["name"]
            assert "installé" not in body, template["name"]

    def test_the_demo_is_linked_once_and_the_first_emails_carry_the_video_thumbnail(self) -> None:
        for template in RECEPTIONIST_EMAIL_TEMPLATES:
            body = str(template["body_html"])
            is_video_template = template["name"] == "Réceptionniste IA - en vidéo"
            shows_the_thumbnail = (
                template["category"] == EmailTemplateCategory.FIRST_EMAIL.value
                and template["name"] not in _SINGLE_DOOR_RECEPTIONIST_EMAILS
            )
            assert body.count("{lien_assistant}") == (0 if is_video_template else 1), template["name"]
            assert body.count("{vignette_video_assistant}") == (1 if shows_the_thumbnail else 0), template["name"]
            assert "{lien_carte}" not in body, template["name"]


class TemplateRow(NamedTuple):
    """The columns of an email template the cut-over may change, read back after a run."""

    name: str
    body_html: str
    is_active: bool


@pytest.fixture
def old_receptionist_row(db: Session) -> int:
    """The admin's « Assistant IA » library row of the previous library, the B template of a past campaign."""
    admin = User(name="Marc Dupont", email=settings.admin_email, hashed_password="x")
    db.add(admin)
    db.flush()
    used_angle = EmailTemplate(
        user_id=admin.id,
        name="Visibilité - on vous cherche",
        subject="ancien objet",
        body_html="<p>ancien corps</p>",
        variables="[]",
        is_active=True,
        category=EmailTemplateCategory.FIRST_EMAIL.value,
        sort_order=0,
        is_library=True,
    )
    old_receptionist = EmailTemplate(
        user_id=admin.id,
        name="Assistant IA - réponses 24/7",
        subject="ancien objet de Assistant IA - réponses 24/7",
        body_html="<p>ancien corps de Assistant IA - réponses 24/7</p>",
        variables="[]",
        is_active=True,
        category=EmailTemplateCategory.FIRST_EMAIL.value,
        sort_order=0,
        is_library=True,
    )
    db.add_all([used_angle, old_receptionist])
    db.flush()
    db.add(
        Campaign(
            user_id=admin.id,
            name="Vague 1",
            status=CampaignStatus.COMPLETED,
            template_id=used_angle.id,
            ab_template_id_b=old_receptionist.id,
        )
    )
    db.commit()
    return old_receptionist.id


def _run_the_cut_over_twice(engine: Engine) -> None:
    for _ in range(2):
        with engine.connect() as connection:
            FrankEmailTemplateLibraryReseed(connection).run()
            connection.commit()


def _rows_by_id(db: Session) -> dict[int, TemplateRow]:
    db.expire_all()
    templates = db.execute(select(EmailTemplate).order_by(EmailTemplate.id)).scalars().all()
    return {template.id: TemplateRow(template.name, template.body_html, template.is_active) for template in templates}


def test_the_receptionist_templates_are_renamed_on_their_own_row(
    engine: Engine, db: Session, old_receptionist_row: int
) -> None:
    _run_the_cut_over_twice(engine)

    rows = _rows_by_id(db)
    renamed = rows[old_receptionist_row]
    assert renamed.name == "Réceptionniste IA - le soir, personne ne répond"
    assert renamed.is_active is True
    assert db.execute(select(Campaign.ab_template_id_b)).scalar_one() == old_receptionist_row
    assert not any(row.name.startswith("Assistant IA") for row in rows.values())


def test_a_renamed_receptionist_row_gets_the_library_body(
    engine: Engine, db: Session, old_receptionist_row: int
) -> None:
    _run_the_cut_over_twice(engine)

    renamed = _rows_by_id(db)[old_receptionist_row]
    library_by_name = {str(template["name"]): template for template in full_email_template_library()}
    assert renamed.body_html == library_by_name[renamed.name]["body_html"]
