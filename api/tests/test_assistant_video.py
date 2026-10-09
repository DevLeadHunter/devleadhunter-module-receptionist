"""The AI-assistant video: its filmed scene, its assembly, its link and its life with the demo."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from core.config import settings
from enums.ai_assistant_status import AiAssistantStatus
from enums.demo_video_status import DemoVideoStatus
from services.ai_assistant.assistant_service import ai_assistant_service
from services.assistant_space_chapter import AssistantSpaceChapter
from services.assistant_widget_clip_service import AssistantWidgetClipService, CapturedFrames
from services.assistant_widget_scene import EXAMPLE_SECONDS, AssistantWidgetScene


def test_the_space_chapter_takes_the_end_of_a_long_enough_segment() -> None:
    """Seven seconds of example space after a widget scene of at least six; nothing on a short clip."""
    assert AssistantSpaceChapter.seconds_for(20) == 7.0
    assert AssistantSpaceChapter.seconds_for(13) == 7.0
    assert AssistantSpaceChapter.seconds_for(12.9) == 0.0
    assert (
        AssistantSpaceChapter.url_for("https://demo.dibodev.fr/ia/toitures-morel?internal=1")
        == "https://demo.dibodev.fr/client/exemple?demo=toitures-morel"
    )
    # A beat at the top, an eased scroll to the requests, then a hold.
    assert AssistantSpaceChapter.scroll_position(0.0, 600) == 0
    assert AssistantSpaceChapter.scroll_position(0.1, 600) == 0
    assert 0 < AssistantSpaceChapter.scroll_position(0.4, 600) < 600
    assert AssistantSpaceChapter.scroll_position(0.6, 600) == 600
    assert AssistantSpaceChapter.scroll_position(1.0, 600) == 600


def test_the_scene_plays_the_example_then_the_slots_where_the_take_names_them() -> None:
    """A 30 s take: the example when « a customer asks » is said, the slots at « an appointment », before the space."""
    plan = AssistantWidgetScene.plan(30, 23)
    assert plan.example_at == pytest.approx(7.2)
    assert plan.booking_at == pytest.approx(19.8)
    assert plan.booking_at >= plan.example_at + EXAMPLE_SECONDS
    assert plan.booking_at <= 23 - 2


def test_the_scene_drops_the_slots_when_they_would_not_stay_on_screen() -> None:
    """A 20 s take leaves 13 s of widget: the example fits, the slots would flash before the space."""
    plan = AssistantWidgetScene.plan(20, 13)
    assert plan.example_at + EXAMPLE_SECONDS <= 13
    assert plan.booking_at is None


def test_the_scene_starts_the_example_early_enough_to_finish_it() -> None:
    """The shortest take still plays its example after a beat on the greeting, even if it cannot end."""
    plan = AssistantWidgetScene.plan(6, 6)
    assert plan.example_at == pytest.approx(0.8)
    assert plan.booking_at is None


def test_the_concat_listing_plays_each_screenshot_for_as_long_as_it_stayed() -> None:
    """The widget frames run from the scene's start to its end at their real pace; chapter frames last 1/fps."""
    frames = CapturedFrames(widget_seconds=2.0, widget=[("w0.jpg", 0.05), ("w1.jpg", 0.8), ("w2.jpg", 1.5)])
    frames.chapter = ["c0.jpg", "c1.jpg"]
    listing = AssistantWidgetClipService.build_concat_listing(frames, fps=25)
    lines = listing.splitlines()
    assert lines[0] == "ffconcat version 1.0"
    durations = [float(line.split(" ")[1]) for line in lines if line.startswith("duration")]
    # The first frame covers the scene from 0, the last widget frame lasts until the scene's end.
    assert durations[:3] == pytest.approx([0.8, 0.7, 0.5])
    assert durations[3:] == pytest.approx([0.04, 0.04])
    assert sum(durations) == pytest.approx(2.08)
    # The concat demuxer ignores the last duration unless its file is listed once more.
    assert lines[-1] == "file 'c1.jpg'"


def test_the_concat_listing_without_a_chapter_repeats_the_last_widget_frame() -> None:
    listing = AssistantWidgetClipService.build_concat_listing(
        CapturedFrames(widget_seconds=1.0, widget=[("w0.jpg", 0.0)]), fps=30
    )
    assert listing.splitlines()[-1] == "file 'w0.jpg'"


def test_a_video_page_link_counts_as_the_assistant_link() -> None:
    """The video page leads to the demo: sending it starts the demo countdown like the demo link itself."""
    assistant = SimpleNamespace(slug="toitures-morel")
    assert ai_assistant_service.body_contains_assistant_link(assistant, "demo.dibodev.fr/va/toitures-morel")
    assert ai_assistant_service.body_contains_assistant_link(assistant, "https://demo.dibodev.fr/ia/toitures-morel")
    assert not ai_assistant_service.body_contains_assistant_link(assistant, "demo.dibodev.fr/v/toitures-morel")


def test_an_expired_demo_loses_its_video_and_a_live_one_keeps_it(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """The /va page closes with the demo: the expiry deletes the video files and resets the video state."""
    purged_slugs: list[str] = []
    monkeypatch.setattr("services.assistant_video_service.delete_files_for_slug", purged_slugs.append)
    now = datetime.now(UTC)
    due, fresh = (
        ai_assistant_service.create(
            db, user_id=1, business_name="Toitures Morel", prospect_id=prospect_id, country="FR", use_brand_color=False
        )
        for prospect_id in (1, 2)
    )
    for assistant in (due, fresh):
        assistant.video_status = DemoVideoStatus.READY.value
        assistant.video_generated_at = now
    ai_assistant_service.start_demo_ttl(db, due, now - timedelta(days=settings.demo_site_ttl_days + 1))
    ai_assistant_service.start_demo_ttl(db, fresh, now)

    ai_assistant_service.expire_due_assistants(db)

    assert purged_slugs == [due.slug]
    assert (due.video_status, due.video_generated_at) == (None, None)
    assert fresh.video_status == DemoVideoStatus.READY.value


def test_deleting_an_assistant_deletes_its_video_files(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from api.v1.routes.ai_assistants import delete_assistant

    purged_slugs: list[str] = []
    monkeypatch.setattr("services.assistant_video_service.delete_files_for_slug", purged_slugs.append)
    assistant = ai_assistant_service.create(
        db, user_id=1, business_name="Toitures Morel", prospect_id=1, country="FR", use_brand_color=False
    )
    assistant.video_status = DemoVideoStatus.READY.value
    db.commit()

    asyncio.run(delete_assistant(assistant.id, SimpleNamespace(id=1), db))

    assert purged_slugs == [assistant.slug]
    assert (assistant.status, assistant.video_status) == (AiAssistantStatus.DELETED.value, None)


def test_the_owner_sees_the_thumbnail_of_a_ready_video_only(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """The detail page previews the thumbnail the emails show, cache-busted by the generation instant."""
    from api.v1.routes.ai_assistants import get_assistant

    monkeypatch.setattr("services.assistant_video_service.r2_storage.public_url", lambda key: f"https://cdn/{key}")
    assistant = ai_assistant_service.create(
        db, user_id=1, business_name="Toitures Morel", prospect_id=1, country="FR", use_brand_color=False
    )
    owner = SimpleNamespace(id=1)

    before = asyncio.run(get_assistant(assistant.id, owner, db))
    assistant.video_status = DemoVideoStatus.READY.value
    assistant.video_generated_at = datetime(2026, 9, 27, 21, 0, tzinfo=UTC)
    db.commit()
    ready = asyncio.run(get_assistant(assistant.id, owner, db))

    assert before.video_thumbnail_url is None
    assert ready.video_thumbnail_url is not None
    assert ready.video_thumbnail_url.startswith("https://cdn/") and assistant.slug in ready.video_thumbnail_url
    assert ready.video_thumbnail_url.endswith(f"?v={int(assistant.video_generated_at.timestamp())}")
