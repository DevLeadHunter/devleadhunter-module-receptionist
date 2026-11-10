"""The receptionist's desktop video build on the sidecar: one detached build, and its failures."""

from __future__ import annotations

import asyncio
import functools
import io
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import scraper_sidecar as sidecar
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.routing import APIRoute

from devleadhunter_receptionist.services.assistant_widget_clip_service import (
    AssistantWidgetClipError,
    assistant_widget_clip_service,
)
from devleadhunter_receptionist.sidecar import (
    PIP_CORNER,
    THUMBNAIL_LABEL,
    capture_receptionist_widget,
    register_receptionist_sidecar_routes,
)
from services import video_pipeline

# The context the API sends for a receptionist video, with the calibration preview's extras.
_RECEPTIONIST_CONTEXT: dict[str, Any] = {
    "slug": "toitures-morel",
    "demo_url": "https://demo.dibodev.fr/ia/toitures-morel",
    "first_name": None,
    "presenter_duration": 40,
    "presenter_intro": 5,
    "presenter_outro": 9,
    "total_seconds": 26,
    "out_width": 1280,
    "out_height": 720,
    "fps": 30,
    "preview": True,
}


def _receptionist_request(slug: str) -> sidecar.DesktopVideoBuildRequest:
    return sidecar.DesktopVideoBuildRequest(**{**_RECEPTIONIST_CONTEXT, "slug": slug, "preview": False})


def _run_receptionist_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, slug: str, capture: Any) -> None:
    async def montage(**kwargs: Any) -> None:
        Path(kwargs["output_video"]).write_bytes(b"video")
        Path(kwargs["output_thumb"]).write_bytes(b"thumbnail")

    monkeypatch.setattr(assistant_widget_clip_service, "build_widget_clip", capture)
    monkeypatch.setattr(sidecar, "_compose_desktop_montage", montage)
    monkeypatch.setattr(sidecar, "_chrome_path", "chrome.exe")
    request = _receptionist_request(slug)
    asyncio.run(
        sidecar._run_desktop_video_build(
            request,
            tmp_path,
            None,
            capture=functools.partial(capture_receptionist_widget, sidecar.SidecarVideoBuilds, request, tmp_path),
            thumbnail_label=THUMBNAIL_LABEL,
            pip_corner=PIP_CORNER,
        )
    )


def _video_build_assistant_full() -> Callable[..., Any]:
    """The receptionist's ``/video/build-assistant-full`` route, as the module adds it to a sidecar."""
    app = FastAPI()
    register_receptionist_sidecar_routes(app, sidecar.SidecarVideoBuilds)
    return next(
        route.endpoint
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/video/build-assistant-full"
    )


def test_the_context_the_api_sends_is_accepted() -> None:
    receptionist = sidecar.SidecarVideoBuilds.parse_request(json.dumps(_RECEPTIONIST_CONTEXT))

    assert (receptionist.slug, receptionist.presenter_intro, receptionist.preview) == ("toitures-morel", 5.0, True)


def test_a_capture_error_ends_the_build_with_its_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def capture(**kwargs: Any) -> None:
        raise AssistantWidgetClipError("L'exemple ne s'est pas joué pendant la capture.")

    _run_receptionist_build(monkeypatch, tmp_path, "garage-echec", capture)

    progress = sidecar._VIDEO_BUILD_PROGRESS["garage-echec"]
    assert (progress["step"], progress["message"]) == ("error", "L'exemple ne s'est pas joué pendant la capture.")
    assert not tmp_path.exists()
    assert "garage-echec" not in sidecar._VIDEO_BUILD_RESULTS


def test_an_unexpected_crash_still_ends_the_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def capture(**kwargs: Any) -> None:
        raise KeyError("total_seconds")

    _run_receptionist_build(monkeypatch, tmp_path, "garage-crash", capture)

    progress = sidecar._VIDEO_BUILD_PROGRESS["garage-crash"]
    assert (progress["step"], progress["message"]) == ("error", "Erreur inattendue : 'total_seconds'")


def test_a_build_longer_than_the_app_waits_is_stopped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(video_pipeline, "MAXIMUM_GENERATION_SECONDS", 0.05)

    def capture(**kwargs: Any) -> None:
        time.sleep(0.5)

    _run_receptionist_build(monkeypatch, tmp_path, "garage-lent", capture)

    progress = sidecar._VIDEO_BUILD_PROGRESS["garage-lent"]
    assert (progress["step"], progress["message"]) == ("error", video_pipeline.GENERATION_OVERRUN_MESSAGE)


def test_the_start_saves_the_uploads_and_keeps_the_detached_build(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    builds: list[tuple[str, Path, Path | None]] = []

    async def build(
        request: sidecar.DesktopVideoBuildRequest, work_dir: Path, photo_path: Path | None, **_options: Any
    ) -> None:
        builds.append((request.slug, work_dir, photo_path))
        assert (work_dir / "presenter.mp4").read_bytes() == b"clip"
        raise RuntimeError("bug after the start")

    monkeypatch.setattr(sidecar, "_run_desktop_video_build", build)
    video_build_assistant_full = _video_build_assistant_full()

    async def start() -> dict[str, object]:
        response = await video_build_assistant_full(
            payload=json.dumps(_RECEPTIONIST_CONTEXT),
            presenter=UploadFile(file=io.BytesIO(b"clip"), filename="presenter.mp4"),
            presenter_photo=None,
        )
        assert len(sidecar._VIDEO_BUILD_TASKS) == 1
        await asyncio.sleep(0.01)
        return response

    with caplog.at_level(logging.ERROR, logger="scraper_sidecar"):
        response = asyncio.run(start())

    assert response == {"started": True, "slug": "toitures-morel"}
    [(slug, work_dir, photo_path)] = builds
    assert (slug, photo_path) == ("toitures-morel", None)
    assert not sidecar._VIDEO_BUILD_TASKS
    assert any(record.getMessage() == "Detached video build died" for record in caplog.records)
    sidecar._discard_video_build_result(slug)
    sidecar._VIDEO_BUILD_PROGRESS.pop(slug, None)
    for leftover in work_dir.iterdir():
        leftover.unlink()
    work_dir.rmdir()


def test_an_invalid_payload_starts_nothing() -> None:
    video_build_assistant_full = _video_build_assistant_full()

    async def start() -> None:
        await video_build_assistant_full(
            payload=json.dumps({**_RECEPTIONIST_CONTEXT, "slug": "../../x"}),
            presenter=UploadFile(file=io.BytesIO(b"clip"), filename="presenter.mp4"),
            presenter_photo=None,
        )

    with pytest.raises(HTTPException) as refusal:
        asyncio.run(start())

    assert refusal.value.status_code == 422
    assert "../../x" not in sidecar._VIDEO_BUILD_PROGRESS
