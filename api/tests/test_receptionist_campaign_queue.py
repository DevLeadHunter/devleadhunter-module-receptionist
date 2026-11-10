"""The receptionist's offer in the core's campaign engine: its send guards, its module, its SMS and its lock."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.orm import Session

import services.campaign_queue_service as cqs
from devleadhunter_receptionist.offer import ReceptionistCampaignOffer
from models.campaign import Campaign
from schemas.campaign import CampaignFollowUpCreate
from services.campaign_follow_up_rules import CampaignFollowUpRules
from services.campaign_offers import CampaignOffers
from services.campaign_queue_service import CampaignQueueService
from services.contact_lock_service import MODULE_WEBSITES, contact_lock_service
from services.sms_config_service import sms_config_service
from services.sms_service import sms_service

_USER_ID = 7
_RECEPTIONIST_MODULE = "ai-assistant"
_NOW: datetime = datetime.now(UTC).replace(tzinfo=None)


class _Result:
    """Stand-in for a SQLAlchemy result exposing the accessors the queue reads."""

    def scalar(self) -> None:
        return None

    def all(self) -> list[object]:
        return []


class _FakeDB:
    """Session stand-in: records adds and commits; nothing stored, so every module follows its default switch."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return _Result()

    def get(self, _model: object, _key: object) -> None:
        return None

    def add(self, row: object) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.commits += 1


def _offer_state(monkeypatch: pytest.MonkeyPatch, *, has_assistant: bool, has_video: bool = False) -> None:
    """Whether the prospect has an active receptionist of the sender, and whether its video is ready."""
    monkeypatch.setattr(
        ReceptionistCampaignOffer, "has_active_offer", lambda _self, _db, *, prospect_id, user_id: has_assistant
    )
    monkeypatch.setattr(ReceptionistCampaignOffer, "has_ready_video", lambda _self, _db, *, prospect_id, user_id: has_video)


def test_the_send_guards_of_the_receptionist_templates(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    linking = SimpleNamespace(subject="Votre réceptionniste", body_html="<p>{lien_assistant}</p>")
    video_only = SimpleNamespace(subject="Votre réceptionniste", body_html="<p>{vignette_video_assistant}</p>")

    def refusal(template: SimpleNamespace, *, include_video: bool = True) -> Any:
        return CampaignOffers.email_send_refusal(
            db, template, prospect_id=1, user_id=_USER_ID, include_video=include_video
        )

    # Assistant template, no active assistant: held back.
    _offer_state(monkeypatch, has_assistant=False)
    assert refusal(linking).reason == "Pas d'assistant IA actif"
    _offer_state(monkeypatch, has_assistant=True)
    assert refusal(linking) is None

    # The receptionist's video as the only door: held back until it exists, and while the video toggle is off.
    missing_video = refusal(video_only)
    assert missing_video is not None and missing_video.is_missing_video
    assert missing_video.reason == "Pas de vidéo de réceptionniste prête"
    _offer_state(monkeypatch, has_assistant=True, has_video=True)
    assert refusal(video_only) is None
    switched_off = refusal(video_only, include_video=False)
    assert switched_off is not None and switched_off.is_missing_video


def test_a_receptionist_video_template_is_video_only_unless_it_carries_the_live_link(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _offer_state(monkeypatch, has_assistant=True, has_video=False)
    video_only = SimpleNamespace(subject="Votre réceptionniste", body_html="<p>{vignette_video_assistant}</p>")
    combo = SimpleNamespace(subject="x", body_html="<p>{vignette_video_assistant} {lien_assistant}</p>")
    plain = SimpleNamespace(subject="x", body_html="<p>{lien_assistant}</p>")

    def is_held_back_for_its_video(template: SimpleNamespace | None) -> bool:
        refusal = CampaignOffers.email_send_refusal(db, template, prospect_id=1, user_id=_USER_ID, include_video=True)
        return refusal is not None and refusal.is_missing_video

    assert is_held_back_for_its_video(video_only) is True
    assert is_held_back_for_its_video(combo) is False
    assert is_held_back_for_its_video(plain) is False
    assert is_held_back_for_its_video(None) is False


def test_campaign_module_reads_every_assistant_variable_and_the_follow_ups() -> None:
    service = CampaignQueueService(_FakeDB())
    price_only = SimpleNamespace(subject="Offre", body_html="Votre assistant pour {prix_assistant}/mois")
    website = SimpleNamespace(subject="Site", body_html="{lien_demo}")
    # A template that only mentions the assistant price is still an assistant offer.
    assert service._campaign_module([price_only]) == _RECEPTIONIST_MODULE
    assert service._campaign_module([website, None]) == cqs.MODULE_WEBSITES
    # A follow-up linking the assistant makes the whole campaign an assistant campaign.
    follow_up = SimpleNamespace(template=SimpleNamespace(subject="Relance", body_html="{lien_assistant}"))
    campaign = SimpleNamespace(follow_ups=[follow_up], follow_up_template_id=None)
    templates = service._campaign_email_templates(campaign, website, None)
    assert service._campaign_module(templates) == _RECEPTIONIST_MODULE


def _enqueue_prospect(pid: int, phone: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=pid,
        phone=phone,
        name=f"Prospect {pid}",
        do_not_contact=False,
        is_dismissed=False,
        contacted_by_module=None,
        contacted_by_module_at=None,
    )


def test_enqueue_sms_assistant_campaign_needs_an_assistant_not_a_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDB()
    svc = CampaignQueueService(db)

    monkeypatch.setattr(cqs.CampaignQueueService, "_purge_skipped_initial_items", lambda self, cid: 0)
    monkeypatch.setattr(
        cqs.CampaignQueueService,
        "_schedule_slots",
        lambda self, campaign, prospects, now, latest: [datetime(2026, 1, 5, 9, 0)] * len(prospects),
    )
    # Nobody has a demo site; everyone but prospect 3 has an active assistant.
    monkeypatch.setattr(cqs.CampaignQueueService, "_active_demo_for_prospect", lambda self, pid, uid: None)
    monkeypatch.setattr(
        ReceptionistCampaignOffer, "has_active_offer", lambda _self, _db, *, prospect_id, user_id: prospect_id != 3
    )
    monkeypatch.setattr(sms_service, "is_suppressed", lambda db, uid, e164: False)

    prospects = [_enqueue_prospect(10, "06 12 34 56 78"), _enqueue_prospect(3, "06 98 76 54 32")]
    campaign = SimpleNamespace(id=1, user_id=7, channel="sms", sms_template_key="assistant-24-7", prospects=prospects)

    result = svc._enqueue_sms(campaign)

    assert [row.prospect_id for row in db.added] == [10]
    assert [entry["id"] for entry in result.skipped_without_offer[_RECEPTIONIST_MODULE]] == [3]
    assert result.skipped_no_demo == []
    assert prospects[0].contacted_by_module == _RECEPTIONIST_MODULE  # the lock is stamped for the right module


def _stamped_prospect(module: str | None, days_ago: int) -> SimpleNamespace:
    """A prospect stub carrying a mobile, an email and the lock columns."""
    return SimpleNamespace(
        id=42,
        name="Garage Martin",
        email="garage@example.com",
        phone="06 12 34 56 78",
        country="FR",
        do_not_contact=False,
        is_dismissed=False,
        email_undeliverable=False,
        contacted_by_module=module,
        contacted_by_module_at=_NOW - timedelta(days=days_ago) if module else None,
    )


def _sms_item(prospect: SimpleNamespace) -> SimpleNamespace:
    """A queued receptionist SMS."""
    campaign = SimpleNamespace(user_id=_USER_ID, channel="sms", sms_template_key="assistant-24-7")
    return SimpleNamespace(
        prospect=prospect,
        campaign=campaign,
        queue_type="initial",
        sms_template_key=None,
        sms_message_id=None,
        status="sending",
        skip_reason=None,
    )


def _stub_sms_dispatch(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Make the campaign SMS path sendable and return the ids of the prospects actually texted."""
    texted: list[int] = []

    async def send_to_prospect(_db: object, **kwargs: Any) -> SimpleNamespace:
        texted.append(kwargs["prospect"].id)
        return SimpleNamespace(sent=True, reason=None, message=None)

    monkeypatch.setattr(sms_config_service, "get", lambda _db, _user_id: SimpleNamespace(sender="GarageMartin"))
    monkeypatch.setattr(sms_service, "legal_window_refusal", lambda country=None: None)
    monkeypatch.setattr(sms_service, "send_to_prospect", send_to_prospect)
    _offer_state(monkeypatch, has_assistant=True)
    monkeypatch.setattr(CampaignQueueService, "_active_demo_for_prospect", lambda _self, _pid, _uid: None)
    monkeypatch.setattr(CampaignQueueService, "_schedule_follow_ups", lambda _self, _item: None)
    return texted


def test_a_receptionist_campaign_sms_skips_a_prospect_the_websites_took_since_the_enqueue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    texted = _stub_sms_dispatch(monkeypatch)
    item = _sms_item(_stamped_prospect(MODULE_WEBSITES, 3))
    db = _FakeDB()

    asyncio.run(CampaignQueueService(db)._dispatch_sms(item))

    assert texted == []
    assert db.commits == 1
    assert item.status == "skipped"
    assert item.skip_reason == "Réservé par un autre module"


def test_a_receptionist_campaign_sms_sent_refreshes_the_receptionist_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reservation made at the enqueue moves to the actual send."""
    texted = _stub_sms_dispatch(monkeypatch)
    prospect = _stamped_prospect(_RECEPTIONIST_MODULE, 20)
    reserved_at: datetime = prospect.contacted_by_module_at
    item = _sms_item(prospect)

    asyncio.run(CampaignQueueService(_FakeDB())._dispatch_sms(item))

    assert texted == [42]
    assert item.status == "sent"
    assert prospect.contacted_by_module == _RECEPTIONIST_MODULE
    assert prospect.contacted_by_module_at > reserved_at


def test_the_lock_names_the_receptionist_by_its_module_label() -> None:
    assert contact_lock_service.module_label(_RECEPTIONIST_MODULE) == "Réceptionniste IA"


def test_a_website_sms_campaign_cannot_relance_with_the_receptionist() -> None:
    sms_campaign = Campaign(user_id=_USER_ID, name="SMS", channel="sms", sms_template_key="direct")
    steps = [CampaignFollowUpCreate(delay_days=3, position=1, sms_template_key="assistant-prix-cash")]

    refusal = CampaignFollowUpRules.refusal(sms_campaign, steps, first_contact_key="direct")

    assert refusal is not None and "même offre" in refusal
