"""Prospection video generation for AI assistants.

The assistant's video is its own thing (a *different* recording from the site video, per the module
brief): the user's assistant-module presenter clip full-screen for the intro/outro, and in the middle
a screen capture of the demo page's chat **answering** — the scripted example plays (a customer writes,
the receptionist asks for a photo and hands the request over), then the appointment slots open
(:mod:`services.assistant_widget_scene`); when the clip leaves enough time, the last seconds switch to the
example client space, where the requests land (:mod:`services.assistant_space_chapter`). The webcam bubble sits
bottom-right so it never covers the chat. Everything but the capture, the storage namespace and the wording is
shared with the site video in :class:`services.prospection_video_service.ProspectionVideoService`.

Rendering happens in a temp dir, then the mp4 + jpg go to Cloudflare R2
(``videos/assistant/{slug}.mp4`` / ``images/assistant/{slug}.jpg``); the player page is the demo host's
``/va/{slug}``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path

from core.config import settings
from enums.ai_assistant_status import AiAssistantStatus
from enums.demo_video_status import DemoVideoStatus
from models.ai_assistant import AiAssistant
from services import video_montage
from services.assistant_space_chapter import AssistantSpaceChapter
from services.assistant_widget_scene import EXAMPLE_NOT_PLAYED_MESSAGE, AssistantWidgetScene
from services.capture_page import CapturePage
from services.prospection_video_service import CapturedSegment, ProspectionVideoService
from services.r2_storage_service import r2_storage
from services.video_pipeline import VideoGenerationError

logger = logging.getLogger(__name__)

# The presenter clip the assistant video uses (a speech about the assistant, not the site).
ASSISTANT_PRESENTER_MODULE = "ai-assistant"


def video_object_key(slug: str) -> str:
    """R2 key of the assistant's generated video."""
    return r2_storage.assistant_video_key(slug)


def thumbnail_object_key(slug: str) -> str:
    """R2 key of the assistant's email thumbnail."""
    return r2_storage.assistant_thumbnail_key(slug)


def video_page_url(slug: str) -> str:
    """Public player page for the assistant's video."""
    return f"{settings.demo_host_base_url.rstrip('/')}/va/{slug}"


def demo_page_url(slug: str) -> str:
    """The assistant's demo page, the one its video films."""
    return f"{settings.demo_host_base_url.rstrip('/')}/ia/{slug}"


def public_video_file_url(slug: str) -> str:
    """Cloudflare URL the player streams the assistant video from."""
    return r2_storage.public_url(video_object_key(slug))


def public_thumbnail_url(slug: str, generated_at: datetime | None = None) -> str:
    """Cloudflare URL of the assistant email thumbnail (cache-busted by ``generated_at``)."""
    url = r2_storage.public_url(thumbnail_object_key(slug))
    if generated_at is not None:
        url = f"{url}?v={int(generated_at.timestamp())}"
    return url


def has_ready_video(assistant: AiAssistant) -> bool:
    """Whether the assistant has a generated, ready-to-serve video."""
    return assistant.video_status == DemoVideoStatus.READY.value


def delete_files_for_slug(slug: str) -> None:
    """Best-effort R2 cleanup of an assistant's video + thumbnail."""
    try:
        r2_storage.delete_many([video_object_key(slug), thumbnail_object_key(slug)])
    except Exception:
        logger.warning("[AssistantVideo] R2 cleanup failed for slug=%s", slug, exc_info=True)


class AssistantVideoService(ProspectionVideoService[AiAssistant]):
    """The prospection video of a receptionist: its capture (the chat answering, then the client space) and its files."""

    subject_model = AiAssistant
    kind = "assistant"
    presenter_module = ASSISTANT_PRESENTER_MODULE
    shown_subject = "la réceptionniste"
    already_running_message = "Une génération est déjà en cours pour cette réceptionniste."
    missing_presenter_message = (
        "Aucun clip de présentation pour la réceptionniste. Enregistrez d'abord votre vidéo webcam "
        "« réceptionniste » dans les paramètres."
    )
    thumbnail_label = video_montage.THUMBNAIL_LABEL_ASSISTANT
    pip_corner = video_montage.PIP_CORNER_RIGHT

    def _check_can_generate(self, assistant: AiAssistant) -> None:
        """
        Refuse a receptionist that is not active.

        Args:
            assistant: The receptionist.

        Raises:
            ValueError: with the reason the dashboard shows.
        """
        if assistant.status != AiAssistantStatus.ACTIVE.value:
            raise ValueError("La vidéo ne peut être générée que pour une réceptionniste active.")

    def _video_key(self, slug: str) -> str:
        """
        The R2 key of the receptionist video.

        Args:
            slug: The receptionist's slug.

        Returns:
            The object key.
        """
        return video_object_key(slug)

    def _thumbnail_key(self, slug: str) -> str:
        """
        The R2 key of the receptionist video's email thumbnail.

        Args:
            slug: The receptionist's slug.

        Returns:
            The object key.
        """
        return thumbnail_object_key(slug)

    def _delete_files(self, slug: str) -> None:
        """
        Delete the receptionist video's files.

        Args:
            slug: The receptionist's slug.
        """
        delete_files_for_slug(slug)

    async def _capture_middle(self, assistant: AiAssistant, middle_seconds: float, work_dir: Path) -> CapturedSegment:
        """
        Record the receptionist's demo page in a headless browser (the VPS path: nothing needs the owner's session).

        Args:
            assistant: The receptionist.
            middle_seconds: How long the middle lasts.
            work_dir: The generation's temporary folder.

        Returns:
            The recording and the chat still.

        Raises:
            VideoGenerationError: when the box is low on memory, the page cannot be captured or the example did
                not play.
        """
        self._guard_capture_memory()
        return await asyncio.to_thread(
            self._capture_assistant_sync, demo_page_url(assistant.slug), middle_seconds, work_dir
        )

    @staticmethod
    def _capture_assistant_sync(url: str, seconds: float, work_dir: Path) -> CapturedSegment:
        """Blocking Playwright capture: the chat framed, the scripted example, the appointment slots, then the space.

        Uses Playwright's SYNC API in a worker thread (a plain thread has no event loop, so spawning
        the browser works on every platform — same reason as the site capture). The example client space
        takes the last seconds when the segment is long enough; when it cannot be shown, the widget holds.

        Args:
            url: The assistant demo page (``/ia/{slug}``); visited with ``?internal=1``.
            seconds: The middle-segment duration to fill with the interaction.
            work_dir: Temp directory receiving the recording + screenshot.

        Returns:
            The recording, the offset of the interaction start inside it, and the chat screenshot.

        Raises:
            VideoGenerationError: when the page cannot be captured or the example did not play.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover — dependency guard
            raise VideoGenerationError(
                "Playwright n'est pas installé (pip install playwright && playwright install chromium)."
            ) from exc

        screenshot_path = work_dir / "top.png"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": video_montage.WIDTH, "height": video_montage.HEIGHT},
                    record_video_dir=str(work_dir),
                    record_video_size={"width": video_montage.WIDTH, "height": video_montage.HEIGHT},
                    # Open the widget in French — the sales video speaks the prospection language.
                    locale="fr-FR",
                )
                page = context.new_page()
                recording_start = time.monotonic()

                CapturePage.open(page, CapturePage.internal_url(url))
                page.wait_for_timeout(1200)

                # Frame the chat whole, then screenshot it before the scene (the product, for the thumbnail).
                try:
                    AssistantWidgetScene.frame(page)
                except Exception as exc:
                    raise VideoGenerationError(f"Le widget ne s'est pas ouvert : {exc}") from exc
                page.wait_for_timeout(900)
                page.screenshot(path=str(screenshot_path))

                scene_start = time.monotonic()
                scroll_offset = scene_start - recording_start
                deadline = scene_start + seconds

                # The widget scene: the scripted example, then the appointment slots when the take leaves room.
                chapter_seconds = AssistantSpaceChapter.seconds_for(seconds)
                widget_seconds = seconds - chapter_seconds
                AssistantWidgetScene.play_in_real_time(
                    page, AssistantWidgetScene.plan(seconds, widget_seconds), scene_start, widget_seconds
                )
                if not AssistantWidgetScene.has_played_example(page):
                    raise VideoGenerationError(EXAMPLE_NOT_PLAYED_MESSAGE)

                # The last chapter: the example space, scrolled to the requests. Never fails the video.
                if chapter_seconds > 0:
                    try:
                        target = AssistantSpaceChapter.open(page, AssistantSpaceChapter.url_for(url))
                        AssistantSpaceChapter.play(page, target, max(0.0, deadline - time.monotonic()))
                    except Exception:
                        logger.warning("Assistant video: the space chapter could not be shown", exc_info=True)
                        remaining_ms = int(max(0.0, deadline - time.monotonic()) * 1000)
                        if remaining_ms > 0:
                            page.wait_for_timeout(remaining_ms)

                video = page.video
                context.close()
                browser.close()
                if video is None:
                    raise VideoGenerationError("Playwright n'a pas produit d'enregistrement vidéo.")
                recording_path = Path(video.path())
        except VideoGenerationError:
            raise
        except Exception as exc:
            raise VideoGenerationError(f"Échec de la capture de la réceptionniste ({url}) : {exc}") from exc

        if not screenshot_path.is_file():
            raise VideoGenerationError("La capture d'écran de la réceptionniste est introuvable.")
        return CapturedSegment(
            recording_path=recording_path, start_seconds=scroll_offset, screenshot_path=screenshot_path
        )


assistant_video_service = AssistantVideoService()
