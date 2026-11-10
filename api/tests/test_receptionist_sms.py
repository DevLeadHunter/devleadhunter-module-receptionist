"""The receptionist's SMS: its family in the library, its fallbacks, its budget, its frank copy, its price and its send.

The library-wide rules of the core (``test_sms_templates.py``, ``test_frank_email_template_library.py``) cover the
website templates only: the receptionist's templates are held to the same rules here.
"""

import asyncio
import re
from types import SimpleNamespace

import pytest
from assistant_fakes import AcceptingSmsProvider, AsyncCallRecorder
from sqlalchemy.orm import Session

import services.sms_service as sms_module
from devleadhunter_receptionist.models.ai_assistant import AiAssistant
from devleadhunter_receptionist.services.assistant_pricing_service import AssistantPricingService
from devleadhunter_receptionist.services.assistant_service import ai_assistant_service
from devleadhunter_receptionist.sms_templates import RECEPTIONIST_SMS_TEMPLATES
from enums.sms_template_category import SmsTemplateCategory
from models.prospect_db import ProspectDB
from models.sms_config import SmsConfig
from services.campaign_offers import CampaignOffers
from services.country_profiles import CountryProfiles
from services.regional_lexicon import RegionalLexicon
from services.sms.gsm_segments import is_gsm7
from services.sms.templates import (
    SMS_TEMPLATE_LIBRARY,
    SmsTemplate,
    find_sms_template,
    list_sms_templates,
    render_sms_template,
    resolve_sms_template,
)
from services.sms_service import SmsService, sms_service
from services.sms_variables import SmsVariables

_USER_ID = 7
# A common case: a first name, an 18-character slug (the link is the heaviest variable) and the sender's phone.
_TYPICAL_VARIABLES: dict[str, str] = {
    "salutation": "Bonjour Geoffrey",
    "entreprise": "Garage Martin Auto",
    "ville": "Poitiers",
    "metier": "garagiste",
    "lien_demo": "demo.dibodev.fr/s/garage-martin-auto",
    "lien_assistant": "demo.dibodev.fr/s/ia/garage-martin-auto",
    "lien_video": "demo.dibodev.fr/s/v/garage-martin-auto",
    "lien_video_assistant": "demo.dibodev.fr/s/va/garage-martin-auto",
    "ancien_site": "garage-martin.fr",
    "prix": "500 €",
    "prix_assistant": "79 €",
    "date_expiration": "12 novembre",
    "prenom_receptionniste": "Sofia",
    "receptionniste": "une réceptionniste",
    "assistant_virtuel": "une assistante virtuelle",
    "telephone": "06 12 34 56 78",
    "signature": "Léo",
}
# A heavier case: a 26-character slug on every link, the longest a real business name usually makes.
_LONG_SLUG_VARIABLES: dict[str, str] = {
    **_TYPICAL_VARIABLES,
    "entreprise": "Plomberie Chauffage Dupont",
    "lien_demo": "demo.dibodev.fr/s/plomberie-chauffage-dupont",
    "lien_assistant": "demo.dibodev.fr/s/ia/plomberie-chauffage-dupont",
    "lien_video": "demo.dibodev.fr/s/v/plomberie-chauffage-dupont",
    "lien_video_assistant": "demo.dibodev.fr/s/va/plomberie-chauffage-dupont",
    "date_expiration": "30 septembre",
}
_PROSPECTING_SEGMENT_BUDGET = 2
_FORBIDDEN_WORDS = re.compile(r"\b(voici|cliquez|ici)\b", re.IGNORECASE)
_GENDERED_RECEPTIONIST_WORDS = re.compile(
    r"\b(il|elle|virtuel|virtuelle|préparée|une réceptionniste|un réceptionniste|la réceptionniste)\b", re.IGNORECASE
)
_VARIABLE = re.compile(r"\{[a-z_]+\}")
_SMS_DOOR_VARIABLES = ("lien_demo", "lien_video", "lien_assistant", "lien_video_assistant", "lien_carte")
_PRICE_VARIABLES = ("prix", "prix_assistant", "prix_carte")


def _as_read_in(country: str, variables: dict[str, str]) -> dict[str, str]:
    """The variables as a prospect of ``country`` reads them: prices in his currency, the sender's phone dialable from there."""
    profile = CountryProfiles.get(country)
    return {
        **variables,
        "prix": profile.format_price(50000),
        "prix_assistant": profile.format_price(7900),
        "telephone": SmsVariables.phone_for(variables["telephone"], country),
    }


def _receptionist_templates(category: SmsTemplateCategory) -> list[SmsTemplate]:
    return [template for template in RECEPTIONIST_SMS_TEMPLATES if template.category is category]


class TestLibraryIntegrity:
    def test_the_receptionist_keys_join_the_library_without_a_clash(self) -> None:
        keys = [template.key for template in list_sms_templates()]
        assert len(keys) == len(set(keys))
        assert len(keys) == len(SMS_TEMPLATE_LIBRARY) + len(RECEPTIONIST_SMS_TEMPLATES)

    def test_no_receptionist_template_writes_the_stop_mention(self) -> None:
        assert all("36180" not in template.body for template in RECEPTIONIST_SMS_TEMPLATES)

    def test_every_receptionist_video_template_declares_a_valid_fallback(self) -> None:
        # A video body with no generated video would render an empty link: unacceptable in a sent SMS.
        for template in RECEPTIONIST_SMS_TEMPLATES:
            if not (template.uses("lien_video") or template.uses("lien_video_assistant")):
                continue
            assert template.fallback_key is not None, template.key
            fallback = find_sms_template(template.fallback_key)
            assert fallback is not None, template.key
            assert fallback.category is template.category, template.key
            assert not fallback.uses("lien_video"), template.key
            assert not fallback.uses("lien_video_assistant"), template.key


class TestAssistantTemplates:
    """The receptionist SMS family links `{lien_assistant}`, not the website demo."""

    _KEYS = ("assistant-24-7", "assistant-langues", "assistant-demandes", "assistant-relance", "assistant-prix-cash")

    def test_assistant_templates_exist_and_link_the_assistant(self) -> None:
        for key in self._KEYS:
            template = find_sms_template(key)
            assert template is not None, key
            assert template.uses("lien_assistant"), key
            assert not template.uses("lien_demo"), key

    def test_assistant_first_contacts_do_not_claim_a_prior_email(self) -> None:
        for key in ("assistant-24-7", "assistant-langues", "assistant-demandes"):
            template = find_sms_template(key)
            assert template is not None and template.category is SmsTemplateCategory.FIRST_CONTACT
            assert "email" not in template.body, key

    def test_assistant_relance_is_a_follow_up_recalling_the_email(self) -> None:
        template = find_sms_template("assistant-relance")
        assert template is not None
        assert template.category is SmsTemplateCategory.FOLLOW_UP
        assert "email" in template.body

    def test_assistant_template_renders_the_assistant_link(self) -> None:
        template = find_sms_template("assistant-24-7")
        assert template is not None
        body = render_sms_template(template.body, _TYPICAL_VARIABLES)
        assert "demo.dibodev.fr/s/ia/garage-martin-auto" in body
        assert _TYPICAL_VARIABLES["lien_demo"] not in body


class TestResolveFallback:
    """The site video says nothing about the receptionist's: only its own video keeps a receptionist video template."""

    def test_receptionist_video_template_waits_for_the_receptionist_video(self) -> None:
        template = find_sms_template("assistant-video")
        assert template is not None
        assert resolve_sms_template(template, video_ready=True, is_module_video_missing=True).key == "assistant-24-7"
        assert resolve_sms_template(template, video_ready=False, is_module_video_missing=False) is template

    def test_receptionist_video_follow_up_falls_back_to_the_receptionist_follow_up(self) -> None:
        template = find_sms_template("assistant-relance-video")
        assert template is not None and template.category is SmsTemplateCategory.FOLLOW_UP
        assert resolve_sms_template(template, video_ready=True, is_module_video_missing=True).key == "assistant-relance"
        assert resolve_sms_template(template, video_ready=False, is_module_video_missing=False) is template

    def test_the_missing_video_is_the_receptionists_own(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        template = find_sms_template("assistant-video")
        assert template is not None
        ready: dict[str, bool] = {"video": False}
        monkeypatch.setattr(
            "devleadhunter_receptionist.offer.ReceptionistCampaignOffer.has_ready_video",
            lambda _self, _db, *, prospect_id, user_id: ready["video"],
        )

        missing = CampaignOffers.sms_missing_video_refusal(db, template, prospect_id=1, user_id=_USER_ID)
        ready["video"] = True
        present = CampaignOffers.sms_missing_video_refusal(db, template, prospect_id=1, user_id=_USER_ID)

        assert missing is not None and missing.is_missing_video
        assert present is None


class TestTwoSegmentBudget:
    def test_every_receptionist_first_contact_fits_two_gsm7_segments(self) -> None:
        for template in _receptionist_templates(SmsTemplateCategory.FIRST_CONTACT):
            for variables in (_TYPICAL_VARIABLES, _LONG_SLUG_VARIABLES):
                for country in ("FR", "CH"):
                    body = sms_service.render_template_body(template, _as_read_in(country, variables))
                    assert is_gsm7(body), f"{template.key} {country}"
                    segments = sms_service.marketing_segment_count(body, country=country)
                    assert segments <= _PROSPECTING_SEGMENT_BUDGET, f"{template.key} {country}: {len(body)} chars"

    def test_every_receptionist_follow_up_stays_in_gsm7_within_two_segments(self) -> None:
        for template in _receptionist_templates(SmsTemplateCategory.FOLLOW_UP):
            for variables in (_TYPICAL_VARIABLES, _LONG_SLUG_VARIABLES):
                for country in ("FR", "CH"):
                    body = sms_service.render_template_body(template, _as_read_in(country, variables))
                    assert is_gsm7(body), f"{template.key} {country}"
                    segments = sms_service.marketing_segment_count(body, country=country)
                    assert segments <= _PROSPECTING_SEGMENT_BUDGET, f"{template.key} {country}: {len(body)} chars"


class TestOneSegmentInFrance:
    def test_every_receptionist_template_fits_one_segment_in_france(self) -> None:
        for template in RECEPTIONIST_SMS_TEMPLATES:
            body = sms_service.compose_within_budget(template, _TYPICAL_VARIABLES, country="FR")
            assert sms_service.marketing_segment_count(body, country="FR") == 1, f"{template.key}: {len(body)} chars"
            assert body.startswith(_TYPICAL_VARIABLES["salutation"]), template.key

    def test_a_long_business_name_keeps_one_segment_by_dropping_the_first_name(self) -> None:
        for template in RECEPTIONIST_SMS_TEMPLATES:
            body = sms_service.compose_within_budget(template, _LONG_SLUG_VARIABLES, country="FR")
            assert sms_service.marketing_segment_count(body, country="FR") == 1, f"{template.key}: {len(body)} chars"


class TestSmsCopyRules:
    def test_every_receptionist_sms_gives_one_price_one_door_and_the_number_to_answer_to(self) -> None:
        for template in RECEPTIONIST_SMS_TEMPLATES:
            doors = sum(template.body.count(f"{{{link}}}") for link in _SMS_DOOR_VARIABLES)
            assert doors == 1, template.key
            assert template.uses("telephone"), template.key
            assert template.uses("signature"), template.key
            prices_used = [price for price in _PRICE_VARIABLES if template.uses(price)]
            assert len(prices_used) == 1, template.key
            assert _FORBIDDEN_WORDS.search(template.body) is None, template.key
            assert "http" not in template.body, template.key

    def test_receptionist_sms_name_it_by_first_name_as_an_ai_with_its_monthly_price(self) -> None:
        assert RECEPTIONIST_SMS_TEMPLATES
        for template in RECEPTIONIST_SMS_TEMPLATES:
            assert template.name.startswith("Réceptionniste IA - "), template.key
            assert template.uses("prenom_receptionniste") and "IA" in template.body, template.key
            assert _GENDERED_RECEPTIONIST_WORDS.search(_VARIABLE.sub("", template.body)) is None, template.key
            assert "{prix_assistant}/mois" in template.body and not template.uses("prix"), template.key
            assert not template.uses("prix_carte"), template.key
            assert "site" not in template.body.lower(), template.key


class _PricingFakeDB:
    """Session stand-in: no enrichment row, no user row, no module switch stored."""

    def execute(self, *_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(scalar_one_or_none=lambda: None)

    def get(self, *_args: object) -> None:
        return None


@pytest.mark.parametrize(
    ("country", "rendered_price"),
    [
        ("FR", "29 €"),
        ("CH", "27 CHF"),
        ("CA", "46 $ CA"),
    ],
)
def test_the_assistant_price_follows_the_prospect_country_in_gsm7(
    country: str, rendered_price: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A converted monthly price reads firm in an SMS too, and stays inside GSM-7."""
    monkeypatch.setattr(ai_assistant_service, "get_active_for_prospect", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(AssistantPricingService, "monthly_price_cents", lambda _db, _uid: 2900)
    prospect = SimpleNamespace(
        id=1, name="Paysagement Tremblay", city="Laval", email="info@tremblay.ca", phone="514 555-0199",
        category="paysagiste", website=None, country=country,
    )  # fmt: skip

    variables = SmsVariables.build_for_prospect(_PricingFakeDB(), user_id=_USER_ID, prospect=prospect)
    template = SmsTemplate(key="prix", name="Prix", category=SmsTemplateCategory.FIRST_CONTACT, body="{prix_assistant}")
    body = sms_service.render_template_body(template, variables)

    assert body == rendered_price
    assert is_gsm7(body)
    assert variables[RegionalLexicon.COUNTRY_KEY] == country


# The sending service is tested with a fixture template rather than the library's, whose copy changes on its own.
_FIXTURE_TEMPLATES: dict[str, SmsTemplate] = {
    "assistant-24-7": SmsTemplate(
        key="assistant-24-7",
        name="Réceptionniste",
        category=SmsTemplateCategory.FIRST_CONTACT,
        body="{salutation}, votre réceptionniste répond à vos clients : {lien_assistant} {signature}",
    ),
}


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> AcceptingSmsProvider:
    """An accepting SMS provider, an open legal window everywhere, a silent notification and the fixture template."""
    monkeypatch.setattr(SmsService, "legal_window_refusal", lambda self, country=None: None)
    monkeypatch.setattr(sms_module.notification_service, "notify_sms_event", AsyncCallRecorder())
    monkeypatch.setattr(sms_module, "find_sms_template", _FIXTURE_TEMPLATES.get)
    return AcceptingSmsProvider()


def _send_receptionist_sms(db: Session, provider: AcceptingSmsProvider, prospect: ProspectDB) -> object:
    config = SmsConfig(user_id=_USER_ID, sender="Dibodev")
    db.add(config)
    db.commit()
    return asyncio.run(
        SmsService(provider=provider).send_to_prospect(
            db,
            user_id=_USER_ID,
            prospect=prospect,
            config=config,
            demo_url="",
            cold=True,
            template_key="assistant-24-7",
        )
    )


def _prospect_with_assistant(db: Session) -> tuple[ProspectDB, AiAssistant]:
    prospect = ProspectDB(
        name="Garage Martin",
        category="Garage automobile",
        phone="06 11 22 33 44",
        country="FR",
        source="google",
        confidence=2,
        user_id=_USER_ID,
    )
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db,
        user_id=_USER_ID,
        business_name="Garage Martin",
        prospect_id=prospect.id,
        country="FR",
        use_brand_color=False,
    )
    return prospect, assistant


def _count_lookups(monkeypatch: pytest.MonkeyPatch, assistant: AiAssistant) -> list[tuple[int, int]]:
    """Answer every lookup of the sender's assistant with *assistant*, recording its scope."""
    lookups: list[tuple[int, int]] = []

    def counting_lookup(db: Session, *, prospect_id: int, user_id: int) -> AiAssistant | None:
        lookups.append((prospect_id, user_id))
        return assistant

    monkeypatch.setattr(ai_assistant_service, "get_active_for_prospect", counting_lookup)
    return lookups


def test_a_receptionist_sms_reads_the_senders_assistant_for_its_link_and_countdown(
    db: Session, provider: AcceptingSmsProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard, the link and the countdown all read the sender's assistant of this prospect."""
    prospect, assistant = _prospect_with_assistant(db)
    lookups = _count_lookups(monkeypatch, assistant)

    outcome = _send_receptionist_sms(db, provider, prospect)

    assert outcome.sent
    assert lookups and set(lookups) == {(prospect.id, _USER_ID)}
    assert provider.texts[0].endswith("/s/ia/garage-martin")
    assert assistant.demo_link_sent_at is not None


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Since the split, the guard (CampaignOffers.sms_enqueue_refusal), the variables (sms_variables) and the "
        "countdown (record_message_sent) each look the assistant up: 3 queries instead of 1."
    ),
)
def test_a_receptionist_sms_looks_its_assistant_up_once(
    db: Session, provider: AcceptingSmsProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The template's fallback, the guard, the link and the countdown all read the same lookup."""
    prospect, assistant = _prospect_with_assistant(db)
    lookups = _count_lookups(monkeypatch, assistant)

    outcome = _send_receptionist_sms(db, provider, prospect)

    assert outcome.sent
    assert lookups == [(prospect.id, _USER_ID)]
