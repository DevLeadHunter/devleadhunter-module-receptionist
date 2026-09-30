"""The receptionist counts like the site: its links say where a visit comes from, and its visits reach the
prospect list, the hot leads and the evening recap."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.orm import Session

import services.behavior_service as behavior_module
import services.notification_service as notification_module
from models.ai_assistant import AiAssistant
from models.demo_site import DemoSite
from models.prospect_db import ProspectDB
from models.push_subscription import PushSubscription
from services.ai_assistant.assistant_service import ai_assistant_service
from services.behavior_service import behavior_service
from services.email_variables import EmailVariables
from services.notification_service import notification_service
from services.sms_variables import SmsVariables

_DEMO_PAGE = "https://demo.dibodev.fr/ia/garage-martin"
_VIDEO_PAGE = "https://demo.dibodev.fr/va/garage-martin"
_RECEPTIONIST = SimpleNamespace(slug="garage-martin", assistant_name="Hugo", demo_link_sent_at=None, expires_at=None)


def _prospect(db: Session, *, name: str = "Garage Martin") -> ProspectDB:
    prospect = ProspectDB(name=name, category="Garage automobile", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    return prospect


def _assistant(db: Session, prospect: ProspectDB) -> AiAssistant:
    return ai_assistant_service.create(
        db, user_id=7, business_name="Garage Martin", prospect_id=prospect.id, country="FR", use_brand_color=False
    )


def _stub_receptionist_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_assistant_service, "get_active_for_prospect", lambda db, *, prospect_id, user_id: _RECEPTIONIST
    )
    monkeypatch.setattr(ai_assistant_service, "page_url", lambda slug: _DEMO_PAGE)
    monkeypatch.setattr(
        EmailVariables,
        "assistant_video_urls",
        staticmethod(lambda assistant: (_VIDEO_PAGE, "https://cdn.dibodev.fr/garage-martin.jpg")),
    )


def test_the_receptionist_email_links_carry_the_channel_and_the_variant(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_receptionist_pages(monkeypatch)

    variables = EmailVariables.build_for_prospect(db, _prospect(db), user_id=7, variant="A")

    assert f'{_DEMO_PAGE}?src=email&v=A"' in variables["lien_assistant"]
    assert variables["lien_video_assistant"] == f"{_VIDEO_PAGE}?src=email&v=A"
    assert f'{_VIDEO_PAGE}?src=email&v=A"' in variables["vignette_video_assistant"]


def test_the_receptionist_sms_links_take_the_short_form_that_stamps_the_sms_channel(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_receptionist_pages(monkeypatch)

    variables = SmsVariables.build_for_prospect(db, user_id=7, prospect=_prospect(db), assistant=_RECEPTIONIST)

    assert variables["lien_assistant"] == "demo.dibodev.fr/s/ia/garage-martin"
    assert variables["lien_video_assistant"] == "demo.dibodev.fr/s/va/garage-martin"


def test_the_prospect_list_and_the_hot_leads_read_the_receptionist_visits(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prospect worked with a receptionist only is no longer « unknown » once its pages are visited."""
    prospect = _prospect(db)
    assistant = _assistant(db, prospect)
    read_slugs: list[list[str]] = []

    async def aggregate(slugs: list[str]) -> dict[str, dict[str, Any]]:
        read_slugs.append(slugs)
        visited = {"pageviews": 4, "visits": 2, "phone_clicks": 0, "contact_clicks": 0, "cta_clicks": 2}
        return {assistant.slug: {**visited, "last_seen": "2026-09-27T10:00:00"}}

    monkeypatch.setattr(behavior_module.posthog_service, "get_aggregate_by_slugs", aggregate)

    temperatures = asyncio.run(behavior_service.get_temperatures(db, 7, [prospect.id]))
    hot_leads = asyncio.run(behavior_service.get_hot_leads(db, 7))

    assert read_slugs == [[assistant.slug], [assistant.slug]]
    assert temperatures[prospect.id]["temperature"] != "unknown"
    assert [lead["prospect_id"] for lead in hot_leads] == [prospect.id]


def test_the_evening_recap_counts_the_receptionist_visits_once_per_slug(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A site and a receptionist of the same prospect share their slug: its visits are counted once."""
    prospect = _prospect(db)
    shared = _assistant(db, prospect)
    other = _assistant(db, _prospect(db, name="Garage Martin Lyon"))
    db.add(
        DemoSite(
            user_id=7,
            prospect_id=prospect.id,
            slug=shared.slug,
            business_name="Garage Martin",
            status="active",
            expires_at=datetime.now(UTC) + timedelta(days=21),
        )
    )
    db.add(PushSubscription(user_id=7, endpoint="https://push.example/leo", p256dh="key", auth="auth"))
    db.commit()
    counted_slugs: list[list[str]] = []
    recaps: list[str] = []

    async def count_visits(slugs: list[str], since: datetime) -> dict[str, int]:
        counted_slugs.append(slugs)
        return {"pageviews": 3, "engaged": 1}

    async def dispatch(**kwargs: Any) -> None:
        recaps.append(kwargs["body"])

    monkeypatch.setattr(notification_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(notification_module.posthog_service, "count_demo_visits_since", count_visits)
    monkeypatch.setattr(notification_service, "_dispatch", dispatch)
    # The recap closes its session, detaching the rows: read their slugs before.
    expected_slugs = [shared.slug, other.slug]

    asyncio.run(notification_service.send_daily_recap())

    assert counted_slugs == [expected_slugs]
    assert len(recaps) == 1 and "3 visites (1 qualifiées)" in recaps[0]
