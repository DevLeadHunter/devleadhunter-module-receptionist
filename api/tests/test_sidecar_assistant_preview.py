"""The desktop build of the receptionist video: a calibration preview comes back as a bare mp4, a real build as a zip."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

import scraper_sidecar as sidecar
from services.assistant_widget_clip_service import assistant_widget_clip_service


def _run_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, slug: str, is_preview: bool) -> dict[str, Any]:
    """Run the detached build with the capture and the montage stubbed, and return what it left for pickup."""

    def fake_capture(**kwargs: Any) -> None:
        Path(kwargs["output_path"]).write_bytes(b"widget")

    async def fake_montage(**kwargs: Any) -> None:
        Path(kwargs["output_video"]).write_bytes(b"video")
        Path(kwargs["output_thumb"]).write_bytes(b"thumbnail")

    monkeypatch.setattr(assistant_widget_clip_service, "build_widget_clip", fake_capture)
    monkeypatch.setattr(sidecar, "_compose_desktop_montage", fake_montage)
    monkeypatch.setattr(sidecar, "_chrome_path", "chrome.exe")
    request = sidecar.DesktopVideoBuildRequest(
        slug=slug,
        demo_url=f"https://demo.dibodev.fr/ia/{slug}",
        total_seconds=30,
        presenter_duration=45,
        presenter_intro=5,
        presenter_outro=10,
        preview=is_preview,
    )

    asyncio.run(sidecar._run_assistant_video_build(request, tmp_path))

    assert sidecar._VIDEO_BUILD_PROGRESS[slug]["step"] == "done"
    return sidecar._VIDEO_BUILD_RESULTS.pop(slug)


def test_a_calibration_preview_is_a_bare_mp4(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    result = _run_build(monkeypatch, tmp_path, slug="toitures-morel", is_preview=True)

    assert (result["media_type"], result["filename"]) == ("video/mp4", "toitures-morel-preview.mp4")
    assert Path(result["path"]).read_bytes() == b"video"


def test_a_real_build_is_the_zip_the_api_expects(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    result = _run_build(monkeypatch, tmp_path, slug="garage-martin", is_preview=False)

    assert (result["media_type"], result["filename"]) == ("application/zip", "garage-martin-video.zip")
