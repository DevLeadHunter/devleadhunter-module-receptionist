"""The receptionist's email variables: ``{lien_assistant}`` and its video, its price, and its ``{date_expiration}``.

``{lien_assistant}`` MUST be a real ``<a>`` anchor like ``{lien_demo}``: Resend's click tracking only rewrites
``href`` attributes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from core.config import settings
from devleadhunter_receptionist.offer import ASSISTANT_LINK, PRICE_ASSISTANT, receptionist_campaign_offer
from devleadhunter_receptionist.services.assistant_pricing_service import AssistantPricingService
from devleadhunter_receptionist.services.assistant_service import ai_assistant_service
from models.prospect_db import ProspectDB
from services.campaign_queue_service import CampaignQueueService
from services.email_variables import EmailVariables

_USER_ID = 7


class _FakeDB:
    """Session stand-in: no demo site, no enrichment row, no user row, no module switch stored."""

    def execute(self, *_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(scalar_one_or_none=lambda: None)

    def get(self, *_args: object) -> None:
        return None


def _stub_active_assistant(monkeypatch: pytest.MonkeyPatch, assistant: object | None) -> list[tuple[int, int]]:
    """Answer every lookup of the sender's assistant with *assistant*, recording the (prospect_id, user_id) asked."""
    lookups: list[tuple[int, int]] = []

    def fake_lookup(db: object, *, prospect_id: int, user_id: int) -> object | None:
        lookups.append((prospect_id, user_id))
        return assistant

    monkeypatch.setattr(ai_assistant_service, "get_active_for_prospect", fake_lookup)
    return lookups


def _assistant(**columns: object) -> SimpleNamespace:
    """A stand-in active assistant: its slug, its first name, no video and an unstarted countdown unless told."""
    values: dict[str, object] = {
        "slug": "agence-immo",
        "assistant_name": "Sofia",
        "video_status": None,
        "video_generated_at": None,
        "demo_link_sent_at": None,
        "expires_at": None,
    }
    values.update(columns)
    return SimpleNamespace(**values)


def _prospect(db: Session, *, owner_id: int) -> ProspectDB:
    prospect = ProspectDB(
        name="Agence Immo", category="Agence immobilière", source="google", confidence=2, user_id=owner_id
    )
    db.add(prospect)
    db.commit()
    return prospect


def test_resolve_expiry_date_falls_back_to_the_assistant_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a demo link, {date_expiration} announces the sender's assistant demo expiry (projected before its first send)."""
    prospect = SimpleNamespace(id=42)
    _stub_active_assistant(
        monkeypatch, _assistant(demo_link_sent_at=datetime(2026, 9, 21, 6, 0), expires_at=datetime(2026, 10, 12, 6, 0))
    )
    assert EmailVariables.resolve_expiry_date(_FakeDB(), prospect, "", user_id=_USER_ID) == "12 octobre"

    _stub_active_assistant(monkeypatch, _assistant())
    expected = EmailVariables.format_expiry_date(datetime.now(UTC) + timedelta(days=settings.demo_site_ttl_days))
    assert EmailVariables.resolve_expiry_date(_FakeDB(), prospect, "", user_id=_USER_ID) == expected


def test_template_using_expiry_date_with_assistant_link_needs_no_demo_site() -> None:
    """{date_expiration} next to {lien_assistant} reads the assistant's expiry: no demo site required."""
    template = SimpleNamespace(
        subject="Dernier rappel",
        body_html="Votre assistant {lien_assistant} reste en ligne jusqu'au {date_expiration}.",
    )
    assert CampaignQueueService._template_uses_demo_link(template) is False


def test_the_assistant_lookup_is_scoped_to_the_prospect_and_the_sender(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The prospect AND the sending user: never another member's assistant on a shared prospect."""
    lookups = _stub_active_assistant(monkeypatch, _assistant())
    shared_prospect = _prospect(db, owner_id=3)

    variables = EmailVariables.build_for_prospect(db, shared_prospect, user_id=_USER_ID)

    assert lookups and set(lookups) == {(shared_prospect.id, _USER_ID)}
    assert "/ia/agence-immo" in variables[ASSISTANT_LINK]


def _assistant_link(db: Session, monkeypatch: pytest.MonkeyPatch, assistant: object | None, variant: str | None) -> str:
    _stub_active_assistant(monkeypatch, assistant)
    variables = receptionist_campaign_offer.email_variables(
        db, _prospect(db, owner_id=_USER_ID), user_id=_USER_ID, include_video=False, variant=variant
    )
    return variables[ASSISTANT_LINK]


def test_the_assistant_link_renders_an_anchor_for_the_active_assistant(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`{lien_assistant}` renders a real anchor to the sender's own assistant demo page."""
    html = _assistant_link(db, monkeypatch, _assistant(), None)
    assert html.startswith("<a ")
    assert "/ia/agence-immo" in html
    assert html.endswith("</a>")


def test_the_assistant_link_carries_the_email_channel_and_the_variant(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Like `{lien_demo}`, the visit it brings reads as an email visit of its A/B variant; the text stays clean."""
    html = _assistant_link(db, monkeypatch, _assistant(), "B")
    assert '/ia/agence-immo?src=email&v=B"' in html
    visible_text = html.split(">", 1)[1].rsplit("</a>", 1)[0]
    assert visible_text.endswith("/ia/agence-immo")


def test_the_assistant_link_is_empty_without_assistant(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """`{lien_assistant}` is empty when the prospect has no active assistant."""
    assert _assistant_link(db, monkeypatch, None, None) == ""


def _ready_assistant() -> SimpleNamespace:
    return _assistant(
        video_status="ready",
        video_generated_at=datetime(2026, 9, 27, 8, 0),
        demo_link_sent_at=datetime(2026, 9, 21, 6, 0),
        expires_at=datetime(2026, 10, 12, 6, 0),
    )


def test_the_link_the_video_and_the_expiry_date_come_from_the_senders_assistant(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    lookups = _stub_active_assistant(monkeypatch, _ready_assistant())
    prospect = _prospect(db, owner_id=_USER_ID)

    variables = EmailVariables.build_for_prospect(db, prospect, user_id=_USER_ID, variant="A")

    assert lookups and set(lookups) == {(prospect.id, _USER_ID)}
    assert "/ia/agence-immo?src=email&v=A" in variables["lien_assistant"]
    assert variables["lien_video_assistant"].endswith("/va/agence-immo?src=email&v=A")
    assert variables["date_expiration"] == "12 octobre"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Since the split, the offer's variables (CampaignOffers.email_variables) and {date_expiration} "
        "(CampaignOffers.expiry_date_without_demo_link) each look the assistant up: 2 queries instead of 1."
    ),
)
def test_the_email_variables_look_the_assistant_up_once(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Its link, its video and the expiry date all come from one lookup of the sender's assistant."""
    lookups = _stub_active_assistant(monkeypatch, _ready_assistant())
    prospect = _prospect(db, owner_id=_USER_ID)

    EmailVariables.build_for_prospect(db, prospect, user_id=_USER_ID, variant="A")

    assert lookups == [(prospect.id, _USER_ID)]


@pytest.mark.parametrize(
    ("country", "assistant_price"),
    [
        ("FR", "29 €"),
        ("CH", "27 CHF"),
        ("CA", "46 $ CA"),
        ("BE", "29 €"),
    ],
)
def test_the_assistant_price_follows_the_prospect_country(
    country: str, assistant_price: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_active_assistant(monkeypatch, None)
    monkeypatch.setattr(AssistantPricingService, "monthly_price_cents", lambda _db, _uid: 2900)
    prospect = SimpleNamespace(
        id=1, name="Paysagement Tremblay", city="Laval", email="info@tremblay.ca", phone="514 555-0199",
        category="paysagiste", website=None, country=country,
    )  # fmt: skip

    variables = EmailVariables.build_for_prospect(_FakeDB(), prospect, sale_price_cents=50000, user_id=_USER_ID)

    assert variables[PRICE_ASSISTANT] == assistant_price
