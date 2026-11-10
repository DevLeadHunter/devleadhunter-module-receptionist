"""The prospection video's shared life, as the receptionist lives it: checks, publication, reset, older clips."""

from __future__ import annotations

import asyncio
import io
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

import services.prospection_video_service as prospection_module
from devleadhunter_receptionist.enums.ai_assistant_status import AiAssistantStatus
from devleadhunter_receptionist.models.ai_assistant import AiAssistant
from devleadhunter_receptionist.services.assistant_service import ai_assistant_service
from devleadhunter_receptionist.services.assistant_video_service import assistant_video_service
from enums.demo_video_status import DemoVideoStatus
from models.presenter_video import PresenterVideo
from services import video_pipeline
from services.prospection_video_service import (
    ALREADY_BUILDING_MESSAGE,
    THUMBNAIL_UPLOAD_FAILED_MESSAGE,
    VIDEO_UPLOAD_FAILED_MESSAGE,
)
from services.r2_storage_service import r2_storage
from services.video_pipeline import DesktopVideoBuilds, VideoGenerationError

_USER_ID = 1
_PROSPECT_ID = 42
_CLIP_CHOSEN_AT = datetime(2026, 10, 9, 8, 0)


class _FakeBucket:
    """The R2 bucket as the tests see it: uploads and deletions recorded, an upload failing for the keys told to."""

    def __init__(self) -> None:
        self.objects: set[str] = set()
        self.deleted: list[str] = []
        self.failing_keys: set[str] = set()

    async def upload_file_async(self, local_path: Path | str, key: str, content_type: str | None = None) -> str:
        if key in self.failing_keys:
            raise RuntimeError("R2 indisponible")
        assert Path(local_path).is_file()
        self.objects.add(key)
        return f"https://cdn/{key}"

    def delete_many(self, keys: list[str]) -> None:
        self.deleted.extend(keys)
        self.objects.difference_update(keys)


def _presenter(*, duration: float = 30.0, intro: float = 5.0, outro: float = 5.0) -> SimpleNamespace:
    return SimpleNamespace(
        duration_seconds=duration, intro_seconds=intro, outro_seconds=outro, auto_generate=False, in_use_since=None
    )


@pytest.fixture
def videos(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    """The video service with a fake bucket, a presenter clip per module and no build under way."""
    bucket = _FakeBucket()
    reenqueued: list[tuple[int | None, int]] = []
    presenter_modules: list[str] = []

    def presenter_of(db: Session, user_id: int, module: str = "websites") -> SimpleNamespace:
        presenter_modules.append(module)
        return _presenter()

    monkeypatch.setattr("services.presenter_video_service.presenter_video_service.get_for_user", presenter_of)
    monkeypatch.setattr(video_pipeline, "desktop_video_builds", DesktopVideoBuilds())
    monkeypatch.setattr(r2_storage, "upload_file_async", bucket.upload_file_async)
    monkeypatch.setattr(r2_storage, "delete_many", bucket.delete_many)
    monkeypatch.setattr(
        prospection_module,
        "reenqueue_campaigns_after_video_ready",
        lambda db, prospect_id, user_id: reenqueued.append((prospect_id, user_id)),
    )
    yield SimpleNamespace(bucket=bucket, reenqueued=reenqueued, presenter_modules=presenter_modules)


def _assistant(db: Session, video_status: str | None = None) -> AiAssistant:
    assistant = ai_assistant_service.create(
        db,
        user_id=_USER_ID,
        business_name="Toitures Morel",
        prospect_id=_PROSPECT_ID,
        country="FR",
        use_brand_color=False,
    )
    assistant.video_status = video_status
    db.commit()
    return assistant


def _is_recent_naive_utc(moment: datetime | None) -> bool:
    now = datetime.now(UTC).replace(tzinfo=None)
    return moment is not None and moment.tzinfo is None and now - timedelta(minutes=1) <= moment <= now


def _desktop_archive() -> io.BytesIO:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("video.mp4", b"video")
        bundle.writestr("thumbnail.jpg", b"thumbnail")
    archive.seek(0)
    return archive


def test_a_receptionist_video_is_asked_with_the_presenter_clip_of_its_module(
    videos: SimpleNamespace, db: Session
) -> None:
    assistant = _assistant(db)
    videos.presenter_modules.clear()

    assistant_video_service.ensure_generation_can_start(db, assistant, _USER_ID)

    assert videos.presenter_modules == [assistant_video_service.presenter_module]


def test_a_receptionist_that_is_not_active_is_refused(videos: SimpleNamespace, db: Session) -> None:
    assistant = _assistant(db)
    assistant.status = AiAssistantStatus.EXPIRED.value

    with pytest.raises(ValueError, match="réceptionniste active"):
        assistant_video_service.ensure_generation_can_start(db, assistant, _USER_ID)


def test_a_receptionist_video_is_refused_without_a_presenter_clip(
    videos: SimpleNamespace, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    monkeypatch.setattr(
        "services.presenter_video_service.presenter_video_service.get_for_user", lambda *args, **kwargs: None
    )

    with pytest.raises(ValueError, match="clip de présentation"):
        assistant_video_service.ensure_generation_can_start(db, assistant, _USER_ID)


def test_a_clip_leaving_too_little_for_the_receptionist_middle_is_refused(
    videos: SimpleNamespace, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    monkeypatch.setattr(
        "services.presenter_video_service.presenter_video_service.get_for_user",
        lambda *args, **kwargs: _presenter(duration=10.0, intro=5.0, outro=4.0),
    )

    with pytest.raises(ValueError, match="trop longues"):
        assistant_video_service.ensure_generation_can_start(db, assistant, _USER_ID)


def test_a_receptionist_video_the_pc_is_building_is_refused(videos: SimpleNamespace, db: Session) -> None:
    assistant = _assistant(db, video_status=DemoVideoStatus.READY.value)
    assistant.video_desktop_requested_at = datetime(2026, 10, 9, 9, 0)
    assistant_video_service.mark_desktop_build_started(assistant)

    with pytest.raises(ValueError, match=ALREADY_BUILDING_MESSAGE):
        assistant_video_service.ensure_generation_can_start(db, assistant, _USER_ID)


def test_the_desktop_receptionist_video_is_published_and_dated_in_naive_utc(
    videos: SimpleNamespace, db: Session
) -> None:
    assistant = _assistant(db)

    asyncio.run(assistant_video_service.store_desktop_video(db, assistant, _desktop_archive()))

    assert assistant.video_status == DemoVideoStatus.READY.value
    assert _is_recent_naive_utc(assistant.video_generated_at)
    assert videos.bucket.objects == {
        assistant_video_service._video_key(assistant.slug),
        assistant_video_service._thumbnail_key(assistant.slug),
    }
    assert videos.reenqueued == [(_PROSPECT_ID, _USER_ID)]


def test_a_desktop_receptionist_video_whose_thumbnail_fails_is_taken_back_down(
    videos: SimpleNamespace, db: Session
) -> None:
    assistant = _assistant(db, video_status=DemoVideoStatus.READY.value)
    videos.bucket.failing_keys = {assistant_video_service._thumbnail_key(assistant.slug)}

    with pytest.raises(VideoGenerationError):
        asyncio.run(assistant_video_service.store_desktop_video(db, assistant, _desktop_archive()))

    db.expire_all()
    assert (assistant.video_status, assistant.video_error) == (
        DemoVideoStatus.FAILED.value,
        THUMBNAIL_UPLOAD_FAILED_MESSAGE,
    )
    assert videos.bucket.objects == set()
    assert assistant_video_service._video_key(assistant.slug) in videos.bucket.deleted


def test_a_desktop_video_whose_upload_fails_ends_failed_without_a_thumbnail(
    videos: SimpleNamespace, db: Session
) -> None:
    assistant = _assistant(db)
    videos.bucket.failing_keys = {assistant_video_service._video_key(assistant.slug)}

    with pytest.raises(VideoGenerationError):
        asyncio.run(assistant_video_service.store_desktop_video(db, assistant, _desktop_archive()))

    db.expire_all()
    assert (assistant.video_status, assistant.video_error) == (
        DemoVideoStatus.FAILED.value,
        VIDEO_UPLOAD_FAILED_MESSAGE,
    )
    assert videos.bucket.objects == set()
    assert videos.reenqueued == []


def test_clearing_a_video_deletes_its_files_and_resets_it(videos: SimpleNamespace, db: Session) -> None:
    assistant = _assistant(db, video_status=DemoVideoStatus.READY.value)
    assistant.video_generated_at = datetime(2026, 10, 1, 9, 0)

    assistant_video_service.clear_video(db, assistant)

    assert (assistant.video_status, assistant.video_generated_at) == (None, None)
    assert set(videos.bucket.deleted) == {
        assistant_video_service._video_key(assistant.slug),
        assistant_video_service._thumbnail_key(assistant.slug),
    }


def _clip_in_use(db: Session, module: str, in_use_since: datetime | None) -> PresenterVideo:
    take = PresenterVideo(
        user_id=_USER_ID,
        module=module,
        is_active=True,
        file_path=f"videos/presenter/{module}.mp4",
        in_use_since=in_use_since,
    )
    db.add(take)
    db.commit()
    return take


def test_the_receptionist_clip_in_use_is_dated_apart_from_the_sites(db: Session) -> None:
    _clip_in_use(db, "websites", _CLIP_CHOSEN_AT)
    _clip_in_use(db, "ai-assistant", _CLIP_CHOSEN_AT - timedelta(days=3))

    assert assistant_video_service.clip_in_use_since(db, _USER_ID) == _CLIP_CHOSEN_AT - timedelta(days=3)


def test_the_dashboard_shows_a_receptionist_video_made_with_the_clip_in_use(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devleadhunter_receptionist.routes.ai_assistants import get_assistant

    monkeypatch.setattr(r2_storage, "public_url", lambda key: f"https://cdn/{key}")
    _clip_in_use(db, "ai-assistant", _CLIP_CHOSEN_AT)
    assistant = _assistant(db, video_status=DemoVideoStatus.READY.value)
    assistant.video_generated_at = _CLIP_CHOSEN_AT + timedelta(hours=1)
    db.commit()
    owner = SimpleNamespace(id=_USER_ID)

    assistant_response = asyncio.run(get_assistant(assistant.id, owner, db))

    assert assistant_response.is_video_made_with_older_clip is False
