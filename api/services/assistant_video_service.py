"""Prospection video generation for AI assistants.

The assistant's video is its own thing (a *different* recording from the site video, per the module
brief): the user's assistant-module presenter clip full-screen for the intro/outro, and in the middle
a screen capture of the widget **answering** — it opens, a question is asked, the grounded reply
writes itself, and the lead form appears. It reuses the site pipeline where nothing differs: the
picture-in-picture ffmpeg montage (:mod:`services.video_montage`), the « Bonjour {Prénom} » overlay,
R2 hosting and the shared generation semaphore. Only the *capture* and the *storage namespace* change.

Rendering happens in a temp dir, then the mp4 + jpg go to Cloudflare R2
(``videos/assistant/{slug}.mp4`` / ``images/assistant/{slug}.jpg``); the player page is the demo host's
``/va/{slug}``.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from core.config import settings
from enums.ai_assistant_status import AiAssistantStatus
from enums.demo_video_status import DemoVideoStatus
from models.ai_assistant import AiAssistant
from models.presenter_video import PresenterVideo
from services import video_montage, video_pipeline
from services.r2_storage_service import r2_storage
from services.video_pipeline import (
    MIN_FREE_MEMORY_MB_FOR_CAPTURE,
    MIN_FREE_MEMORY_MB_FOR_MONTAGE,
    MIN_SCROLL_SECONDS,
    VideoGenerationError,
    generation_semaphore,
    guard_memory,
)

logger = logging.getLogger(__name__)

# The presenter clip the assistant video uses (a speech about the assistant, not the site).
_PRESENTER_MODULE = "ai-assistant"


def video_object_key(slug: str) -> str:
    """R2 key of the assistant's generated video."""
    return r2_storage.assistant_video_key(slug)


def thumbnail_object_key(slug: str) -> str:
    """R2 key of the assistant's email thumbnail."""
    return r2_storage.assistant_thumbnail_key(slug)


def video_page_url(slug: str) -> str:
    """Public player page for the assistant's video."""
    return f"{settings.demo_host_base_url.rstrip('/')}/va/{slug}"


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


class AssistantVideoService:
    """Generates and serves the AI assistant's prospection video."""

    def request_generation(self, db: Session, assistant: AiAssistant, user_id: int) -> AiAssistant:
        """Validate and start a background generation for an assistant.

        Args:
            db: Active database session.
            assistant: The assistant to make a video for.
            user_id: Owner (used to fetch the assistant-module presenter clip).

        Returns:
            The assistant with ``video_status`` set to ``pending``.

        Raises:
            ValueError: when the assistant or presenter clip is not ready.
        """
        from services.presenter_video_service import presenter_video_service

        if assistant.status != AiAssistantStatus.ACTIVE.value:
            raise ValueError("La vidéo ne peut être générée que pour un assistant actif.")
        if assistant.video_status in (DemoVideoStatus.PENDING.value, DemoVideoStatus.GENERATING.value):
            raise ValueError("Une génération est déjà en cours pour cet assistant.")

        presenter = presenter_video_service.get_for_user(db, user_id, _PRESENTER_MODULE)
        if presenter is None:
            raise ValueError(
                "Aucun clip de présentation pour l'assistant. Enregistrez d'abord votre vidéo webcam "
                "« assistant » dans les paramètres."
            )
        middle_seconds = presenter.duration_seconds - presenter.intro_seconds - presenter.outro_seconds
        if middle_seconds < MIN_SCROLL_SECONDS:
            raise ValueError(
                "Intro + outro trop longues : il reste "
                f"{middle_seconds:.0f}s pour montrer l'assistant (minimum {MIN_SCROLL_SECONDS:.0f}s)."
            )

        assistant.video_status = DemoVideoStatus.PENDING.value
        assistant.video_error = None
        db.commit()
        db.refresh(assistant)

        asyncio.create_task(self._run_generation(assistant.id, user_id))
        return assistant

    def reconcile_orphaned(self, db: Session) -> int:
        """Mark assistants left mid-generation as failed (called once at startup)."""
        orphaned = (
            db.query(AiAssistant)
            .filter(AiAssistant.video_status.in_([DemoVideoStatus.PENDING.value, DemoVideoStatus.GENERATING.value]))
            .all()
        )
        for assistant in orphaned:
            assistant.video_status = DemoVideoStatus.FAILED.value
            assistant.video_error = "Génération interrompue (redémarrage du serveur) — relancez-la."
        if orphaned:
            db.commit()
        return len(orphaned)

    def clear_video(self, db: Session, assistant: AiAssistant) -> AiAssistant:
        """Delete the generated video files and reset the assistant's video state."""
        delete_files_for_slug(assistant.slug)
        assistant.video_status = None
        assistant.video_error = None
        assistant.video_generated_at = None
        db.commit()
        db.refresh(assistant)
        return assistant

    async def _run_generation(self, assistant_id: int, user_id: int) -> None:
        """Background task: own DB session, serialized by the shared generation semaphore."""
        from core.database import SessionLocal
        from services.presenter_video_service import presenter_video_service

        async with generation_semaphore:
            db: Session = SessionLocal()
            try:
                assistant = db.query(AiAssistant).filter(AiAssistant.id == assistant_id).first()
                if assistant is None:
                    return
                presenter = presenter_video_service.get_for_user(db, user_id, _PRESENTER_MODULE)
                if presenter is None:
                    assistant.video_status = DemoVideoStatus.FAILED.value
                    assistant.video_error = "Aucun clip de présentation « assistant » configuré."
                    db.commit()
                    return

                assistant.video_status = DemoVideoStatus.GENERATING.value
                db.commit()

                first_name = video_pipeline.resolve_first_name(db, assistant.prospect_id)
                source_dir = Path(tempfile.mkdtemp(prefix=f"assistant-presenter-src-{user_id}-"))
                try:
                    presenter_path = await video_pipeline.resolve_presenter_file(presenter, source_dir)
                    photo_path = await video_pipeline.resolve_presenter_photo(db, user_id, source_dir)
                    await self._generate(assistant, presenter, presenter_path, first_name, photo_path)
                except VideoGenerationError as exc:
                    assistant.video_status = DemoVideoStatus.FAILED.value
                    assistant.video_error = str(exc)[:1000]
                    db.commit()
                    logger.warning("Assistant video generation failed for slug=%s: %s", assistant.slug, exc)
                    return
                except Exception as exc:
                    assistant.video_status = DemoVideoStatus.FAILED.value
                    assistant.video_error = f"Erreur inattendue : {exc}"[:1000]
                    db.commit()
                    logger.exception("Assistant video generation crashed for slug=%s", assistant.slug)
                    return
                finally:
                    shutil.rmtree(source_dir, ignore_errors=True)

                assistant.video_status = DemoVideoStatus.READY.value
                assistant.video_error = None
                assistant.video_generated_at = datetime.now(UTC)
                db.commit()
                logger.info("Assistant prospection video ready for slug=%s", assistant.slug)
            finally:
                db.close()

    async def _generate(
        self,
        assistant: AiAssistant,
        presenter: PresenterVideo,
        presenter_path: Path,
        first_name: str | None,
        presenter_photo_path: Path | None,
    ) -> None:
        """Capture the widget answering, compose the video, build the thumbnail, publish to R2."""
        middle_seconds = presenter.duration_seconds - presenter.intro_seconds - presenter.outro_seconds
        work_dir = Path(tempfile.mkdtemp(prefix=f"assistant-video-{assistant.slug}-"))
        try:
            guard_memory(MIN_FREE_MEMORY_MB_FOR_CAPTURE, "générer")
            demo_url = f"{settings.demo_host_base_url.rstrip('/')}/a/{assistant.slug}"
            capture_path, scroll_offset, screenshot_path = await asyncio.to_thread(
                self._capture_assistant_sync, demo_url, middle_seconds, work_dir
            )

            output_path = work_dir / "output.mp4"
            thumbnail_path = work_dir / "thumbnail.jpg"
            guard_memory(MIN_FREE_MEMORY_MB_FOR_MONTAGE, "assembler")
            try:
                await asyncio.to_thread(
                    video_montage.compose_final,
                    ffmpeg_path=settings.ffmpeg_path,
                    presenter_duration=presenter.duration_seconds,
                    presenter_intro=presenter.intro_seconds,
                    presenter_outro=presenter.outro_seconds,
                    presenter_path=presenter_path,
                    capture_path=capture_path,
                    scroll_offset=scroll_offset,
                    scroll_seconds=middle_seconds,
                    first_name=first_name,
                    screenshot_path=screenshot_path,
                    output_video=output_path,
                    output_thumbnail=thumbnail_path,
                    presenter_photo_path=presenter_photo_path,
                )
            except video_montage.VideoMontageError as exc:
                raise VideoGenerationError(str(exc)) from exc

            await r2_storage.upload_file_async(output_path, video_object_key(assistant.slug), "video/mp4")
            await r2_storage.upload_file_async(thumbnail_path, thumbnail_object_key(assistant.slug), "image/jpeg")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _capture_assistant_sync(self, url: str, seconds: float, work_dir: Path) -> tuple[Path, float, Path]:
        """Blocking Playwright capture: the widget opening, answering a question, and the lead form.

        Uses Playwright's SYNC API in a worker thread (a plain thread has no event loop, so spawning
        the browser works on every platform — same reason as the site capture).

        Args:
            url: The assistant demo page (``/a/{slug}``); visited with ``?internal=1``.
            seconds: The middle-segment duration to fill with the interaction.
            work_dir: Temp directory receiving the recording + screenshot.

        Returns:
            (capture webm path, offset of the interaction start inside the recording, screenshot path).

        Raises:
            VideoGenerationError: when the page cannot be captured.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover — dependency guard
            raise VideoGenerationError(
                "Playwright n'est pas installé (pip install playwright && playwright install chromium)."
            ) from exc

        screenshot_path = work_dir / "top.png"
        internal_url = url + ("&" if "?" in url else "?") + "internal=1"
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

                try:
                    page.goto(internal_url, wait_until="networkidle", timeout=45000)
                except Exception:
                    page.goto(internal_url, wait_until="load", timeout=45000)
                page.wait_for_timeout(1200)

                # Open the widget, then screenshot the page with it open (the product, for the thumbnail).
                try:
                    page.click(".ai-launcher", timeout=8000)
                    page.wait_for_selector(".ai-panel", timeout=8000)
                except Exception as exc:
                    raise VideoGenerationError(f"Le widget ne s'est pas ouvert : {exc}") from exc
                page.wait_for_timeout(900)
                page.screenshot(path=str(screenshot_path))

                scroll_start = time.monotonic()
                scroll_offset = scroll_start - recording_start
                deadline = scroll_start + seconds

                # Ask a question by clicking the first suggested reply (localised, always present).
                try:
                    page.click(".ai-chips button", timeout=4000)
                except Exception:
                    pass  # No chips (already messaged) — the greeting alone still reads well.

                # Wait for the grounded reply: a second assistant bubble appears after the greeting.
                try:
                    page.wait_for_function("document.querySelectorAll('.ai-m--assistant').length >= 2", timeout=14000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)

                # Show the lead capture near the end, then hold on it until the segment is filled.
                if deadline - time.monotonic() > 4:
                    try:
                        page.click(".ai-book__open", timeout=2000)
                    except Exception:
                        pass
                remaining_ms = int(max(0.0, deadline - time.monotonic()) * 1000)
                if remaining_ms > 0:
                    page.wait_for_timeout(remaining_ms)

                video = page.video
                context.close()
                browser.close()
                if video is None:
                    raise VideoGenerationError("Playwright n'a pas produit d'enregistrement vidéo.")
                capture_path = Path(video.path())
        except VideoGenerationError:
            raise
        except Exception as exc:
            raise VideoGenerationError(f"Échec de la capture de l'assistant ({url}) : {exc}") from exc

        if not screenshot_path.is_file():
            raise VideoGenerationError("La capture d'écran de l'assistant est introuvable.")
        return capture_path, scroll_offset, screenshot_path


assistant_video_service = AssistantVideoService()
