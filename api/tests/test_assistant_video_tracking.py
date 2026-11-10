"""The receptionist's video page (/va): its beacons notify under the assistant module, a robot's visit pushes nothing,
and its events feed the prospect's timeline and score."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

import api.v1.routes.demo_events as demo_events_routes
import services.notification_service as notification_module
from devleadhunter_receptionist.models.ai_assistant import AiAssistant
from devleadhunter_receptionist.services.assistant_service import ai_assistant_service
from devleadhunter_receptionist.services.receptionist_notifications import receptionist_notifications
from models.demo_site import DemoSite
from models.prospect_db import ProspectDB
from schemas.notification import DemoEventIn
from services import lead_scoring
from services.behavior_service import behavior_service
from services.notification_service import notification_service
from services.robot_visit_detector import VisitorBrowser


def _assistant(db: Session, *, prospect_id: int = 42) -> AiAssistant:
    return ai_assistant_service.create(
        db, user_id=7, business_name="Garage Martin", prospect_id=prospect_id, country="FR", use_brand_color=False
    )


def _site(db: Session, *, slug: str, prospect_id: int = 42) -> DemoSite:
    site = DemoSite(
        user_id=7,
        prospect_id=prospect_id,
        slug=slug,
        business_name="Garage Martin",
        status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db.add(site)
    db.commit()
    return site


def test_a_video_page_beacon_notifies_the_receptionist_even_when_a_site_shares_its_slug(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The /va slug names the assistant: the site of the same name is never credited with the view."""
    site_events: list[str] = []
    assistant_events: list[dict[str, Any]] = []

    async def notify_site(_db: Session, **kwargs: Any) -> None:
        site_events.append(kwargs["event_name"])

    async def notify_assistant(_db: Session, **kwargs: Any) -> None:
        assistant_events.append(kwargs)

    monkeypatch.setattr(demo_events_routes.notification_service, "notify_demo_event", notify_site)
    monkeypatch.setattr(receptionist_notifications, "notify_assistant_video_event", notify_assistant)
    assistant = _assistant(db)
    _site(db, slug=assistant.slug, prospect_id=99)

    for event in ("assistant_video_opened", "assistant_video_play"):
        payload = DemoEventIn(demo_slug=assistant.slug, event=event, channel="email")
        asyncio.run(demo_events_routes.ingest_demo_event(payload, db))
    unknown_slug_beacon = DemoEventIn(demo_slug="inconnu", event="assistant_video_play")
    asyncio.run(demo_events_routes.ingest_demo_event(unknown_slug_beacon, db))

    assert site_events == []
    assert [(event["event_name"], event["user_id"], event["prospect_id"]) for event in assistant_events] == [
        ("assistant_video_opened", 7, 42),
        ("assistant_video_play", 7, 42),
    ]
    assert {event["channel"] for event in assistant_events} == {"email"}


def test_a_receptionist_video_push_is_tagged_with_the_assistant_module(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Opened, play, complete and replay push like the site video's; the rest of the player stays analytics-only."""
    pushed: list[dict[str, Any]] = []
    logged: list[dict[str, Any]] = []

    async def dispatch(**kwargs: Any) -> None:
        pushed.append(kwargs)

    monkeypatch.setattr(notification_service, "_dispatch", dispatch)
    monkeypatch.setattr(notification_module.activity_log_service, "record", lambda **kwargs: logged.append(kwargs))

    for event in ("assistant_video_complete", "assistant_video_pause"):
        asyncio.run(
            receptionist_notifications.notify_assistant_video_event(
                db, user_id=7, prospect_id=None, event_name=event, fallback_name="garage-martin", channel="sms"
            )
        )

    assert [(push["title"], push["body"], push["category"]) for push in pushed] == [
        ("✅ garage-martin", "🤖 Assistant IA · A vu ta vidéo en entier · SMS", "assistant")
    ]
    assert [(entry["category"], entry["action"]) for entry in logged] == [("assistant", "assistant_video_complete")]


def test_the_scanner_on_the_receptionist_video_page_pushes_nothing(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hotmail link scanner's visit is only logged, like on a demo; the prospect's own visit still pushes."""
    pushed: list[dict[str, Any]] = []
    logged: list[dict[str, Any]] = []

    async def dispatch(**kwargs: Any) -> None:
        pushed.append(kwargs)

    monkeypatch.setattr(notification_service, "_dispatch", dispatch)
    monkeypatch.setattr(notification_module.activity_log_service, "record", lambda **kwargs: logged.append(kwargs))
    prospect = ProspectDB(name="Perrier Élec", category="Électricien", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    hotmail_scanner = VisitorBrowser(timezone_name="America/Los_Angeles", language="en-US")

    for browser in (hotmail_scanner, VisitorBrowser("Europe/Paris", "fr-FR")):
        asyncio.run(
            receptionist_notifications.notify_assistant_video_event(
                db,
                user_id=7,
                prospect_id=prospect.id,
                event_name="assistant_video_opened",
                fallback_name="perrierelec",
                browser=browser,
            )
        )

    assert [push["body"] for push in pushed] == ["🤖 Assistant IA · A ouvert ta vidéo"]
    assert [entry["action"] for entry in logged] == ["robot_visit_ignored", "assistant_video_opened"]


def test_the_receptionist_video_scores_like_the_site_video() -> None:
    """The /va page's assistant_video_* events feed the same video signals as the site's /v page."""
    site = lead_scoring.compute(
        [
            {"event": "demo_video_play", "timestamp": "t", "properties": {}},
            {"event": "demo_video_complete", "timestamp": "t", "properties": {}},
            {"event": "demo_video_watch_time", "timestamp": "t", "properties": {"seconds": 31}},
        ]
    )
    receptionist = lead_scoring.compute(
        [
            {"event": "assistant_video_play", "timestamp": "t", "properties": {}},
            {"event": "assistant_video_complete", "timestamp": "t", "properties": {}},
            {"event": "assistant_video_watch_time", "timestamp": "t", "properties": {"seconds": 31}},
        ]
    )
    assert receptionist["signals"] == site["signals"]
    assert receptionist["score"] == site["score"] > 0


def test_the_timeline_reads_the_receptionists_slugs_beside_the_sites_each_once(db: Session) -> None:
    """A deleted receptionist and another prospect's stay out; a slug shared by a site and a receptionist is read once."""
    shared = _assistant(db)
    second = _assistant(db)
    deleted = _assistant(db)
    deleted.deleted_at = datetime.now(UTC)
    _assistant(db, prospect_id=43)
    _site(db, slug=shared.slug)
    _site(db, slug="garage-martin-vitrine")

    slugs = behavior_service._slugs_for_prospect(db, 7, 42)

    assert slugs == [shared.slug, "garage-martin-vitrine", second.slug]
