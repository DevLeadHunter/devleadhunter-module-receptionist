"""Render the assistant video's *middle segment*: a screen capture of the public widget answering.

This is the desktop counterpart of :meth:`assistant_video_service.AssistantVideoService._capture_assistant_sync`
(the VPS path). It runs in the bundled sidecar, so — exactly like :mod:`services.storyblok_editor_clip_service`
— it captures **frame by frame** (screenshots + the system ffmpeg) with the machine's own Chrome, never
Playwright's ``record_video`` (whose bundled ffmpeg the frozen sidecar has no copy of).

Unlike the site background, this needs **no authenticated session**: the widget is public, so the capture
is a plain headless recording of ``/ia/{slug}?internal=1`` opening, answering a suggested question, and
revealing the lead form; the last seconds switch to the example client space, where the requests land
(:mod:`services.assistant_space_chapter`, shared with the VPS capture). The VPS montage later overlays the
webcam PiP and the « Bonjour {Prénom} » pill.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from services import video_montage
from services.assistant_space_chapter import AssistantSpaceChapter

logger = logging.getLogger(__name__)

# The widget interaction is scripted against these frame milestones (fractions of the segment): open a
# beat, ask a question, let the grounded reply write, then reveal the lead form and hold on it.
_ASK_QUESTION_AT = 0.12
_OPEN_LEAD_FORM_AT = 0.72


class AssistantWidgetClipError(Exception):
    """Raised when the assistant widget clip cannot be produced."""


class AssistantWidgetClipService:
    """Produce the assistant video's widget-answering middle segment (desktop sidecar)."""

    def __init__(self, ffmpeg_path: str | None = None) -> None:
        self._ffmpeg = ffmpeg_path or os.environ.get("FFMPEG_PATH") or "ffmpeg"

    def build_widget_clip(
        self,
        *,
        demo_url: str,
        output_path: Path,
        screenshot_path: Path,
        executable_path: str | None = None,
        total_seconds: float,
        out_width: int = 1280,
        out_height: int = 720,
        fps: int = 30,
        on_progress: Callable[[str], None] | None = None,
    ) -> tuple[Path, Path]:
        """Record the widget answering to ``output_path`` and grab the product screenshot.

        Args:
            demo_url: The assistant page (``/ia/{slug}``); visited with ``?internal=1``.
            output_path: Where the assembled middle-segment mp4 is written.
            screenshot_path: Where the widget-open screenshot (thumbnail base) is written.
            executable_path: Chrome binary to drive (the sidecar's bundled/installed one).
            total_seconds: Duration the segment must fill (the presenter clip's middle).
            out_width: Output width in pixels.
            out_height: Output height in pixels.
            fps: Output frame rate.
            on_progress: Optional callback invoked with the phase (``widget_capture`` / ``widget_assemble``).

        Returns:
            ``(output_path, screenshot_path)``.

        Raises:
            AssistantWidgetClipError: when Playwright is missing or the widget cannot be captured.
        """
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError as exc:  # pragma: no cover — dependency guard
            raise AssistantWidgetClipError("Playwright n'est pas installé.") from exc

        work_dir = Path(tempfile.mkdtemp(prefix="assistant-widget-clip-"))
        frames_dir = work_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        try:
            if on_progress:
                on_progress("widget_capture")
            self._capture_frames(
                demo_url, frames_dir, screenshot_path, executable_path, total_seconds, out_width, out_height, fps
            )
            if on_progress:
                on_progress("widget_assemble")
            self._assemble(frames_dir, output_path, out_width, out_height, fps)
            return output_path, screenshot_path
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _capture_frames(
        self,
        demo_url: str,
        frames_dir: Path,
        screenshot_path: Path,
        executable_path: str | None,
        total_seconds: float,
        out_width: int,
        out_height: int,
        fps: int,
    ) -> None:
        """Screenshot the widget answering into a numbered frame sequence."""
        from playwright.sync_api import sync_playwright

        total_frames = max(1, round(fps * total_seconds))
        chapter_frames = round(fps * AssistantSpaceChapter.seconds_for(total_seconds))
        widget_frames = max(1, total_frames - chapter_frames)
        ask_at = max(1, round(widget_frames * _ASK_QUESTION_AT))
        open_form_at = max(ask_at + 1, round(widget_frames * _OPEN_LEAD_FORM_AT))
        interval_ms = max(8, round(1000 / fps))
        internal_url = self._as_internal_url(demo_url)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, executable_path=executable_path)
                # Open the widget in French — the sales video speaks the prospection language.
                context = browser.new_context(viewport={"width": out_width, "height": out_height}, locale="fr-FR")
                page = context.new_page()
                try:
                    page.goto(internal_url, wait_until="networkidle", timeout=45000)
                except Exception:
                    page.goto(internal_url, wait_until="load", timeout=45000)
                page.wait_for_timeout(1000)

                try:
                    page.click(".ai-launcher", timeout=8000)
                    page.wait_for_selector(".ai-panel", timeout=8000)
                except Exception as exc:
                    raise AssistantWidgetClipError(f"Le widget ne s'est pas ouvert : {exc}") from exc
                page.wait_for_timeout(700)
                # Product open → the still that becomes the email thumbnail.
                page.screenshot(path=str(screenshot_path))

                asked = False
                form_opened = False
                for index in range(widget_frames):
                    if index == ask_at and not asked:
                        # Ask a question by clicking the first suggested reply (localised, always present).
                        try:
                            page.click(".ai-chips button", timeout=3000)
                        except Exception:
                            pass  # No chips (already messaged) — the greeting alone still reads well.
                        asked = True
                    if index == open_form_at and not form_opened:
                        try:
                            page.click(".ai-book__open", timeout=2000)
                        except Exception:
                            pass
                        form_opened = True
                    page.screenshot(path=str(frames_dir / f"f{index:05d}.png"))
                    page.wait_for_timeout(interval_ms)

                # The last chapter: the example space, scrolled to the requests (the widget holds when it fails).
                target: int | None = None
                if chapter_frames > 0:
                    try:
                        target = AssistantSpaceChapter.open(page, AssistantSpaceChapter.url_for(demo_url))
                    except Exception:
                        logger.warning("Assistant clip: the space chapter could not be shown", exc_info=True)
                for index in range(chapter_frames):
                    if target is not None:
                        position = AssistantSpaceChapter.scroll_position(index / chapter_frames, target)
                        page.evaluate(f"window.scrollTo(0, {position})")
                    page.screenshot(path=str(frames_dir / f"f{widget_frames + index:05d}.png"))
                    page.wait_for_timeout(interval_ms)

                context.close()
                browser.close()
        except AssistantWidgetClipError:
            raise
        except Exception as exc:
            raise AssistantWidgetClipError(f"Capture de l'assistant échouée ({demo_url}) : {exc}") from exc

        if not any(frames_dir.iterdir()):
            raise AssistantWidgetClipError("Aucune image de l'assistant capturée.")
        if not screenshot_path.is_file():
            raise AssistantWidgetClipError("La capture d'écran de l'assistant est introuvable.")

    def _assemble(self, frames_dir: Path, output_path: Path, out_width: int, out_height: int, fps: int) -> None:
        """Assemble the frame sequence into an mp4 with the system ffmpeg (all idle cores, low priority)."""
        args = [
            self._ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "f%05d.png"),
            "-vf",
            f"scale={out_width}:{out_height}",
            *video_montage.x264_encode_flags(fps),
            # Desktop: every idle core, below-normal priority — keeps the user's PC responsive.
            "-threads",
            video_montage.FFMPEG_THREADS_AUTO,
            str(output_path),
        ]
        command, run_kwargs = video_montage.as_background_priority_process(args)
        result = subprocess.run(command, capture_output=True, text=True, **run_kwargs)
        if result.returncode != 0:
            raise AssistantWidgetClipError(f"ffmpeg a échoué : {result.stderr[-400:]}")

    @staticmethod
    def _as_internal_url(url: str) -> str:
        """Add ``internal=1`` so a capture visit is excluded from tracking/notifications."""
        parts = urlparse(url)
        query = dict(parse_qsl(parts.query))
        query["internal"] = "1"
        return urlunparse(parts._replace(query=urlencode(query)))


assistant_widget_clip_service = AssistantWidgetClipService()
