"""Reliability + validation guards for AI-assistant video generation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from enums.ai_assistant_status import AiAssistantStatus
from enums.demo_video_status import DemoVideoStatus
from services import video_pipeline
from services.assistant_space_chapter import AssistantSpaceChapter
from services.assistant_video_service import AssistantVideoService
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
    with pytest.raises(ValueError, match="actif"):
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
