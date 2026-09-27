"""Render the assistant video's *middle segment*: a screen capture of the public widget answering.

This is the desktop counterpart of :meth:`assistant_video_service.AssistantVideoService._capture_assistant_sync`
(the VPS path). It runs in the bundled sidecar with the machine's own Chrome and assembles screenshots with the
system ffmpeg, never Playwright's ``record_video`` (whose bundled ffmpeg the frozen sidecar has no copy of) —
exactly like :mod:`services.storyblok_editor_clip_service`.

Unlike the site background, this needs **no authenticated session**: the widget is public, so the capture is a
plain headless visit of ``/ia/{slug}?internal=1`` playing the scene of :mod:`services.assistant_widget_scene`
(the scripted example, then the appointment slots); the last seconds switch to the example client space, where
the requests land (:mod:`services.assistant_space_chapter`, shared with the VPS capture). The widget scene runs
on the page's own clock (its replies are typed with timers), so its screenshots are timestamped and assembled
at their real pace; the space chapter scrolls frame by frame. The VPS montage later overlays the webcam PiP and
the « Bonjour {Prénom} » pill.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from services import video_montage
from services.assistant_space_chapter import AssistantSpaceChapter
from services.assistant_widget_scene import AssistantSceneProgress, AssistantWidgetScene

logger = logging.getLogger(__name__)

# JPEG screenshots are several times faster to take than PNG: more frames per second of real time.
_JPEG_QUALITY = 90
_LISTING_NAME = "frames.ffconcat"


class AssistantWidgetClipError(Exception):
    """Raised when the assistant widget clip cannot be produced."""


@dataclass
class CapturedFrames:
    """The screenshots of one capture, in order: the timed widget scene, then the space chapter."""

    widget_seconds: float
    widget: list[tuple[str, float]] = field(default_factory=list)
    chapter: list[str] = field(default_factory=list)


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
            screenshot_path: Where the chat screenshot (thumbnail base) is written.
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
            frames = self._capture_frames(
                demo_url, frames_dir, screenshot_path, executable_path, total_seconds, out_width, out_height, fps
            )
            if on_progress:
                on_progress("widget_assemble")
            (frames_dir / _LISTING_NAME).write_text(self.build_concat_listing(frames, fps), encoding="utf-8")
            self._assemble(frames_dir, output_path, out_width, out_height, fps, total_seconds)
            return output_path, screenshot_path
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    @staticmethod
    def build_concat_listing(frames: CapturedFrames, fps: int) -> str:
        """
        Write the ffconcat listing that plays each screenshot for as long as it stayed on screen.

        A widget frame lasts until the next one was taken (the first one from the scene's start, the last one
        until the scene's end); a chapter frame lasts one output frame.

        Args:
            frames: The captured screenshots.
            fps: The output frame rate.

        Returns:
            The listing, ready for ffmpeg's concat demuxer.
        """
        lines: list[str] = ["ffconcat version 1.0"]
        for index, (name, taken_at) in enumerate(frames.widget):
            starts_at = 0.0 if index == 0 else taken_at
            is_last = index + 1 == len(frames.widget)
            ends_at = frames.widget_seconds if is_last else frames.widget[index + 1][1]
            lines += [f"file '{name}'", f"duration {max(ends_at - starts_at, 0.001):.4f}"]
        for name in frames.chapter:
            lines += [f"file '{name}'", f"duration {1 / fps:.4f}"]
        listed_names: list[str] = frames.chapter or [name for name, _ in frames.widget]
        if listed_names:
            # The concat demuxer ignores the last entry's duration unless that file is listed once more.
            lines.append(f"file '{listed_names[-1]}'")
        return "\n".join(lines) + "\n"

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
    ) -> CapturedFrames:
        """Screenshot the widget scene against the clock, then the space chapter frame by frame."""
        from playwright.sync_api import sync_playwright

        chapter_seconds = AssistantSpaceChapter.seconds_for(total_seconds)
        widget_seconds = max(0.1, total_seconds - chapter_seconds)
        chapter_frame_count = round(fps * chapter_seconds)
        plan = AssistantWidgetScene.plan(total_seconds, widget_seconds)
        frames = CapturedFrames(widget_seconds=widget_seconds)
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
                    AssistantWidgetScene.frame(page)
                except Exception as exc:
                    raise AssistantWidgetClipError(f"Le widget ne s'est pas ouvert : {exc}") from exc
                page.wait_for_timeout(700)
                # The chat before the scene becomes the still of the email thumbnail.
                page.screenshot(path=str(screenshot_path))

                progress = AssistantSceneProgress()
                started = time.monotonic()
                while (elapsed := time.monotonic() - started) < widget_seconds:
                    AssistantWidgetScene.play_due_steps(page, plan, elapsed, progress)
                    name = f"w{len(frames.widget):05d}.jpg"
                    page.screenshot(path=str(frames_dir / name), type="jpeg", quality=_JPEG_QUALITY)
                    frames.widget.append((name, elapsed))
                    # No need for more than the output rate: wait for the next frame slot when ahead of it.
                    ahead_seconds = started + len(frames.widget) / fps - time.monotonic()
                    if ahead_seconds > 0:
                        page.wait_for_timeout(ahead_seconds * 1000)

                # The last chapter: the example space, scrolled to the requests (the widget holds when it fails).
                target: int | None = None
                if chapter_frame_count > 0:
                    try:
                        target = AssistantSpaceChapter.open(page, AssistantSpaceChapter.url_for(demo_url))
                    except Exception:
                        logger.warning("Assistant clip: the space chapter could not be shown", exc_info=True)
                for index in range(chapter_frame_count):
                    if target is not None:
                        position = AssistantSpaceChapter.scroll_position(index / chapter_frame_count, target)
                        page.evaluate(f"window.scrollTo(0, {position})")
                    name = f"c{index:05d}.jpg"
                    page.screenshot(path=str(frames_dir / name), type="jpeg", quality=_JPEG_QUALITY)
                    frames.chapter.append(name)

                context.close()
                browser.close()
        except AssistantWidgetClipError:
            raise
        except Exception as exc:
            raise AssistantWidgetClipError(f"Capture de la réceptionniste échouée ({demo_url}) : {exc}") from exc

        if not frames.widget:
            raise AssistantWidgetClipError("Aucune image de la réceptionniste capturée.")
        if not screenshot_path.is_file():
            raise AssistantWidgetClipError("La capture d'écran de la réceptionniste est introuvable.")
        return frames

    def _assemble(
        self, frames_dir: Path, output_path: Path, out_width: int, out_height: int, fps: int, total_seconds: float
    ) -> None:
        """Assemble the timed screenshots into a constant-rate mp4 with the system ffmpeg (idle cores, low priority)."""
        args = [
            self._ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(frames_dir / _LISTING_NAME),
            "-vf",
            f"fps={fps},scale={out_width}:{out_height}",
            "-t",
            f"{total_seconds:.3f}",
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
