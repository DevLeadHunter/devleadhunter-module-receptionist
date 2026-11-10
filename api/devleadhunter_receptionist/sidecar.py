"""The receptionist's route on the desktop sidecar: its prospection video, built on the owner's PC like a site's."""

from __future__ import annotations

import asyncio
import functools
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, UploadFile

from core.product_modules.sidecar import SidecarVideoBuildApi, SidecarVideoBuildRequest

# The words after « Bonjour {Prénom} » on the email thumbnail of the receptionist's video.
THUMBNAIL_LABEL: str = "votre réceptionniste en vidéo"
# The webcam bubble takes the right-hand corner, clear of the chat.
PIP_CORNER: str = "right"
_STEP_MESSAGES: dict[str, str] = {
    "widget_capture": "Capture de la réceptionniste (réponse en direct)…",
    "widget_assemble": "Assemblage de la séquence réceptionniste…",
}


async def capture_receptionist_widget(
    video_builds: SidecarVideoBuildApi, request: SidecarVideoBuildRequest, work_dir: Path
) -> tuple[Path, Path]:
    """
    Film the middle of a receptionist video (the widget answering), with the chat before the scene as the still.

    Args:
        video_builds: The sidecar's video build machinery.
        request: The validated build.
        work_dir: The build's folder.

    Returns:
        The widget mp4 and the still.

    Raises:
        AssistantWidgetClipError: when the widget cannot be filmed or its example did not play.
    """
    from devleadhunter_receptionist.services.assistant_widget_clip_service import assistant_widget_clip_service

    widget_path = work_dir / "widget.mp4"
    screenshot_path = work_dir / video_builds.screenshot_file_name

    def report_step(step: str) -> None:
        video_builds.report_progress(request.slug, step, _STEP_MESSAGES.get(step))

    await asyncio.to_thread(
        assistant_widget_clip_service.build_widget_clip,
        demo_url=request.demo_url,
        output_path=widget_path,
        screenshot_path=screenshot_path,
        executable_path=video_builds.chrome_executable(),
        total_seconds=request.total_seconds,
        out_width=request.out_width,
        out_height=request.out_height,
        fps=request.fps,
        on_progress=report_step,
    )
    return widget_path, screenshot_path


def register_receptionist_sidecar_routes(app: FastAPI, video_builds: SidecarVideoBuildApi) -> None:
    """
    Add ``/video/build-assistant-full`` to the sidecar: the complete desktop build of a receptionist's video.

    Args:
        app: The sidecar's application.
        video_builds: The sidecar's video build machinery.
    """

    @app.post("/video/build-assistant-full", dependencies=[Depends(video_builds.require_token)])
    async def video_build_assistant_full(
        payload: str = Form(...),
        presenter: UploadFile = File(...),
        presenter_photo: UploadFile | None = File(default=None),
    ) -> object:
        """
        START the complete desktop assistant-video build (widget capture + montage) and return at once.

        Same detached contract as ``/video/build-full``: returns ``{"started": true}``, the app polls
        ``/video/build-progress`` until ``done``/``error``, then fetches the file from ``/video/build-result``. Unlike
        the site build there is no Storyblok session to resolve — the assistant widget is public, so this never needs
        a login. ``422`` when the payload is invalid.
        """
        request = video_builds.parse_request(payload)
        return await video_builds.start(
            request,
            presenter,
            presenter_photo,
            capture=functools.partial(capture_receptionist_widget, video_builds),
            thumbnail_label=THUMBNAIL_LABEL,
            pip_corner=PIP_CORNER,
            # The default message names a Storyblok session, which only the site build opens.
            preparing_message="Préparation (clip présentateur)…",
        )
