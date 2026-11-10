"""A receptionist's prospection video waits for the owner's desktop app like a site's: asked, taken, built or failed."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import devleadhunter_receptionist.routes.ai_assistants as ai_assistants_routes
from core.database import get_db
from devleadhunter_receptionist.enums.ai_assistant_status import AiAssistantStatus
from devleadhunter_receptionist.models.ai_assistant import AiAssistant
from devleadhunter_receptionist.routes.ai_assistants import router as ai_assistants_router
from devleadhunter_receptionist.services.assistant_service import ai_assistant_service
from devleadhunter_receptionist.services.assistant_video_service import assistant_video_service
from enums.demo_site_status import DemoSiteStatus
from enums.demo_video_status import DemoVideoStatus
from models.demo_site import DemoSite
from services import video_pipeline
from services.auth_service import get_current_active_user
from services.demo_video_service import demo_video_service
from services.prospect_search.desktop_app_presence import DesktopAppPresence
from services.prospection_video_desktop_relay import ProspectionVideoDesktopRelay
from services.r2_storage_service import r2_storage
from services.video_pipeline import DesktopVideoBuilds

_USER_ID = 1
_OTHER_USER_ID = 2
_STORYBLOK_SPACE_ID = 287465


def _presenter_clip(*, auto_generate: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        duration_seconds=30.0, intro_seconds=5.0, outro_seconds=5.0, auto_generate=auto_generate, in_use_since=None
    )


@pytest.fixture(autouse=True)
def presenter_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every user has a presenter clip long enough to show a site or a receptionist."""
    monkeypatch.setattr(
        "services.presenter_video_service.presenter_video_service.get_for_user",
        lambda *args, **kwargs: _presenter_clip(),
    )


@pytest.fixture(autouse=True)
def builds(monkeypatch: pytest.MonkeyPatch) -> DesktopVideoBuilds:
    """No build under way at the start of a test."""
    fresh_builds = DesktopVideoBuilds()
    monkeypatch.setattr(video_pipeline, "desktop_video_builds", fresh_builds)
    return fresh_builds


@pytest.fixture(autouse=True)
def public_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """The published videos have their public address, without a configured storage."""
    monkeypatch.setattr(r2_storage, "public_url", lambda key: f"https://cdn/{key}")


def _site(db: Session, slug: str) -> DemoSite:
    site = DemoSite(
        user_id=_USER_ID,
        slug=slug,
        business_name=slug.replace("-", " ").title(),
        status=DemoSiteStatus.ACTIVE.value,
        demo_url=f"https://demo.dibodev.fr/{slug}",
        storyblok_space_id=_STORYBLOK_SPACE_ID,
        expires_at=datetime.now(UTC) + timedelta(days=21),
    )
    db.add(site)
    db.commit()
    return site


def _assistant(db: Session, user_id: int = _USER_ID, video_status: str | None = None) -> AiAssistant:
    assistant = ai_assistant_service.create(
        db, user_id=user_id, business_name="Toitures Morel", prospect_id=None, country="FR", use_brand_color=False
    )
    assistant.video_status = video_status
    db.commit()
    return assistant


def _site_relay() -> ProspectionVideoDesktopRelay[DemoSite]:
    return ProspectionVideoDesktopRelay(demo_video_service)


def _assistant_relay() -> ProspectionVideoDesktopRelay[AiAssistant]:
    return ProspectionVideoDesktopRelay(assistant_video_service)


def test_the_builds_of_a_site_and_a_receptionist_with_the_same_id_stay_apart(db: Session) -> None:
    site = _site(db, "garage-martin")
    assistant = _assistant(db)
    assert assistant.id == site.id
    _site_relay().request(db, site, _USER_ID)
    _assistant_relay().request(db, assistant, _USER_ID)

    _site_relay().claim(site)

    assert demo_video_service.is_desktop_build_started(site) is True
    assert assistant_video_service.is_desktop_build_started(assistant) is False


def test_a_receptionist_request_waits_then_the_desktop_app_takes_and_fails_it(db: Session) -> None:
    relay = _assistant_relay()
    assistant = _assistant(db, video_status=DemoVideoStatus.READY.value)

    relay.request(db, assistant, _USER_ID)
    waiting = relay.waiting_subjects(db, _USER_ID)
    relay.claim(assistant)
    waiting_while_built = relay.waiting_subjects(db, _USER_ID)
    relay.record_failure(db, assistant, "Le widget ne s'est pas ouvert.")

    assert [subject.id for subject in waiting] == [assistant.id]
    assert waiting_while_built == []
    assert (assistant.video_status, assistant.video_error) == (
        DemoVideoStatus.READY.value,
        "Le widget ne s'est pas ouvert.",
    )
    assert assistant.video_desktop_requested_at is None


def test_an_inactive_receptionist_is_neither_asked_nor_handed_over(db: Session) -> None:
    relay = _assistant_relay()
    assistant = _assistant(db)
    relay.request(db, assistant, _USER_ID)

    assistant.status = AiAssistantStatus.EXPIRED.value
    db.commit()

    assert relay.waiting_subjects(db, _USER_ID) == []
    with pytest.raises(ValueError, match="réceptionniste active"):
        relay.request(db, assistant, _USER_ID)


def test_no_receptionist_request_is_left_when_the_clip_does_not_generate_on_its_own_or_is_missing(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)

    assert _assistant_relay().request_if_auto_generating(db, assistant, _USER_ID) is False
    monkeypatch.setattr(
        "services.presenter_video_service.presenter_video_service.get_for_user", lambda *args, **kwargs: None
    )
    assert _assistant_relay().request_if_auto_generating(db, assistant, _USER_ID) is False
    assert assistant.video_desktop_requested_at is None


def test_a_new_receptionist_asks_the_pc_for_its_video_when_its_clip_generates_on_its_own(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "services.presenter_video_service.presenter_video_service.get_for_user",
        lambda *args, **kwargs: _presenter_clip(auto_generate=True),
    )

    assistant = _assistant(db)

    assert assistant.video_desktop_requested_at is not None
    assert [subject.id for subject in _assistant_relay().waiting_subjects(db, _USER_ID)] == [assistant.id]


def _client(db: Session, router: Any, user_id: int = _USER_ID) -> TestClient:
    """The given routes, called by a signed-in user on the test database."""
    application = FastAPI()
    application.include_router(router)
    signed_in_user: Any = SimpleNamespace(id=user_id)
    application.dependency_overrides[get_current_active_user] = lambda: signed_in_user
    application.dependency_overrides[get_db] = lambda: db
    return TestClient(application)


@pytest.fixture
def presence(monkeypatch: pytest.MonkeyPatch) -> DesktopAppPresence:
    """A fresh desktop presence behind the receptionist routes."""
    fresh_presence = DesktopAppPresence()
    monkeypatch.setattr(ai_assistants_routes, "desktop_app_presence", fresh_presence)
    return fresh_presence


def test_a_receptionist_video_goes_through_the_same_relay_routes(db: Session, presence: DesktopAppPresence) -> None:
    assistant = _assistant(db)
    prefix = ai_assistants_router.prefix
    client = _client(db, ai_assistants_router)

    asked = client.post(f"{prefix}/{assistant.id}/video/desktop-request")
    waiting = client.get(f"{prefix}/video/desktop-requests")
    claimed = client.post(f"{prefix}/{assistant.id}/video/desktop-claim")
    building = client.get(f"{prefix}/{assistant.id}/video/state")
    failed = client.post(
        f"{prefix}/{assistant.id}/video/desktop-failure", json={"message": "Le widget ne s'est pas ouvert."}
    )

    assert asked.status_code == 202
    assert asked.json()["video_desktop_requested_at"] is not None
    assert [request["assistant_id"] for request in waiting.json()] == [assistant.id]
    assert presence.is_online(_USER_ID) is True
    assert claimed.json()["is_video_desktop_build_started"] is True
    assert building.json()["is_video_desktop_build_started"] is True
    assert failed.json()["video_status"] == DemoVideoStatus.FAILED.value
    assert failed.json()["video_error"] == "Le widget ne s'est pas ouvert."
    assert client.post(f"{prefix}/{assistant.id}/video").status_code == 405


def test_a_receptionist_request_is_withdrawn_but_never_while_it_is_built(
    db: Session, presence: DesktopAppPresence
) -> None:
    withdrawn_assistant = _assistant(db)
    built_assistant = _assistant(db)
    prefix = ai_assistants_router.prefix
    client = _client(db, ai_assistants_router)
    client.post(f"{prefix}/{withdrawn_assistant.id}/video/desktop-request")
    client.post(f"{prefix}/{built_assistant.id}/video/desktop-request")
    client.post(f"{prefix}/{built_assistant.id}/video/desktop-claim")

    withdrawn = client.delete(f"{prefix}/{withdrawn_assistant.id}/video/desktop-request")
    refused = client.delete(f"{prefix}/{built_assistant.id}/video/desktop-request")
    deleted = client.delete(f"{prefix}/{built_assistant.id}/video")

    assert withdrawn.status_code == 200
    assert withdrawn.json()["video_desktop_requested_at"] is None
    assert [refused.status_code, deleted.status_code] == [409, 409]
    assert (
        _client(db, ai_assistants_router, user_id=_OTHER_USER_ID)
        .get(f"{prefix}/{built_assistant.id}/video/state")
        .status_code
        == 404
    )
