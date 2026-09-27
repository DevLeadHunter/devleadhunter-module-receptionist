"""Reliability + validation guards for AI-assistant video generation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from enums.ai_assistant_status import AiAssistantStatus
from enums.demo_video_status import DemoVideoStatus
from services import video_pipeline
from services.ai_assistant.assistant_service import ai_assistant_service
from services.assistant_space_chapter import AssistantSpaceChapter
from services.assistant_video_service import AssistantVideoService
from services.assistant_widget_clip_service import AssistantWidgetClipService, CapturedFrames
from services.assistant_widget_scene import EXAMPLE_SECONDS, AssistantWidgetScene
from services.video_pipeline import VideoGenerationError


class _FakeQuery:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def filter(self, *args: object, **kwargs: object) -> _FakeQuery:
        return self

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeDB:
    def __init__(self, rows: list[SimpleNamespace] | None = None) -> None:
        self._rows = rows or []
        self.committed = False

    def query(self, *args: object, **kwargs: object) -> _FakeQuery:
        return _FakeQuery(self._rows)

    def commit(self) -> None:
        self.committed = True

    def refresh(self, *args: object, **kwargs: object) -> None:
        pass


def _assistant(assistant_id: int, *, status: str, video_status: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=assistant_id,
        slug=f"assistant-{assistant_id}",
        status=status,
        video_status=video_status,
        video_error=None,
        video_generated_at=None,
        prospect_id=None,
    )


def _presenter(*, duration: float, intro: float, outro: float, auto_generate: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        duration_seconds=duration, intro_seconds=intro, outro_seconds=outro, auto_generate=auto_generate
    )


def _patch_presenter(monkeypatch: pytest.MonkeyPatch, presenter: SimpleNamespace | None) -> None:
    monkeypatch.setattr(
        "services.presenter_video_service.presenter_video_service.get_for_user",
        lambda *args, **kwargs: presenter,
    )


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


def test_reconcile_marks_orphaned_generations_failed() -> None:
    rows = [
        _assistant(1, status=AiAssistantStatus.ACTIVE.value, video_status=DemoVideoStatus.GENERATING.value),
        _assistant(2, status=AiAssistantStatus.ACTIVE.value, video_status=DemoVideoStatus.PENDING.value),
    ]
    db = _FakeDB(rows)

    count = AssistantVideoService().reconcile_orphaned(db)

    assert count == 2
    assert db.committed is True
    for assistant in rows:
        assert assistant.video_status == DemoVideoStatus.FAILED.value
        assert assistant.video_error  # a user-facing reason is set


def test_reconcile_without_orphans_does_not_commit() -> None:
    db = _FakeDB([])

    count = AssistantVideoService().reconcile_orphaned(db)

    assert count == 0
    assert db.committed is False


def test_request_generation_refuses_inactive_assistant() -> None:
    assistant = _assistant(1, status=AiAssistantStatus.DELETED.value)
    with pytest.raises(ValueError, match="réceptionniste active"):
        AssistantVideoService().request_generation(_FakeDB(), assistant, user_id=1)


def test_request_generation_refuses_when_already_running() -> None:
    assistant = _assistant(1, status=AiAssistantStatus.ACTIVE.value, video_status=DemoVideoStatus.GENERATING.value)
    with pytest.raises(ValueError, match="déjà en cours"):
        AssistantVideoService().request_generation(_FakeDB(), assistant, user_id=1)


def test_request_generation_refuses_without_presenter_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_presenter(monkeypatch, None)
    assistant = _assistant(1, status=AiAssistantStatus.ACTIVE.value)
    with pytest.raises(ValueError, match="clip de présentation"):
        AssistantVideoService().request_generation(_FakeDB(), assistant, user_id=1)


def test_request_generation_refuses_when_middle_too_short(monkeypatch: pytest.MonkeyPatch) -> None:
    # intro + outro eat almost the whole clip → less than the minimum for the widget capture.
    _patch_presenter(monkeypatch, _presenter(duration=10.0, intro=5.0, outro=4.0))
    assistant = _assistant(1, status=AiAssistantStatus.ACTIVE.value)
    with pytest.raises(ValueError, match="trop longues"):
        AssistantVideoService().request_generation(_FakeDB(), assistant, user_id=1)


def test_auto_generation_skips_without_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_presenter(monkeypatch, None)
    assistant = _assistant(1, status=AiAssistantStatus.ACTIVE.value)
    assert AssistantVideoService().maybe_start_auto_generation(_FakeDB(), assistant, user_id=1) is False


def test_auto_generation_skips_when_toggle_off(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_presenter(monkeypatch, _presenter(duration=20.0, intro=4.0, outro=5.0, auto_generate=False))
    assistant = _assistant(1, status=AiAssistantStatus.ACTIVE.value)
    assert AssistantVideoService().maybe_start_auto_generation(_FakeDB(), assistant, user_id=1) is False


def test_shared_memory_guard_refuses_when_low(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(video_pipeline, "available_memory_mb", lambda: 300.0)
    with pytest.raises(VideoGenerationError):
        video_pipeline.guard_memory(video_pipeline.MIN_FREE_MEMORY_MB_FOR_CAPTURE, "générer")


def test_shared_memory_guard_allows_when_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    # None = /proc/meminfo unreadable (e.g. non-Linux) → never block generation.
    monkeypatch.setattr(video_pipeline, "available_memory_mb", lambda: None)
    video_pipeline.guard_memory(video_pipeline.MIN_FREE_MEMORY_MB_FOR_CAPTURE, "générer")  # must not raise
