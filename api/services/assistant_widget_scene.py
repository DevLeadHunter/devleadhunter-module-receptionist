"""
The widget scene of the assistant video: what the capture films before the example-space chapter.

The demo page (``/ia/{slug}``) lays the chat out already open, beside the business's phone. The scene frames
that chat so it is whole in the 1280×720 capture, then plays the page's scripted example (a customer writes,
the receptionist asks for a photo and hands the request over) and, when the take leaves room, opens the
appointment slots. The spoken middle take names the same steps in the same order — a question, a photo, an
appointment, then the space — so each step starts where the prompter reaches it. Both captures share this
script: the VPS one (Playwright's recording, real time) and the desktop one (timestamped screenshots).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# The chat's lower edge stays this far above the bottom of the capture.
_FRAME_MARGIN_PX = 24
# Where the spoken middle take reaches « a customer asks » and « he wants an appointment » (share of the take).
_EXAMPLE_SHARE = 0.24
_BOOKING_SHARE = 0.66
# The scripted example runs about five seconds: two customer turns and two typed replies.
EXAMPLE_SECONDS = 5.5
# A beat on the greeting before the example, and the least time the slots stay on screen before the space.
_FIRST_BEAT_SECONDS = 0.8
_BOOKING_MIN_SECONDS = 2.0

_LAUNCHER_SELECTOR = ".ai-launcher"
_PANEL_SELECTOR = ".ai-panel"
_EXAMPLE_CHIP_SELECTOR = ".ai-chip--example"
_FIRST_CHIP_SELECTOR = ".ai-chips button"
_APPOINTMENT_CHIP_SELECTOR = ".ai-chip--appointment"

# Blur first (while the chat holds the focus the page does not scroll), then bring the chat's lower edge into view.
_FRAME_SCRIPT = (
    "(margin) => {"
    " if (document.activeElement instanceof HTMLElement) document.activeElement.blur();"
    " const panel = document.querySelector('.ai-panel');"
    " const bottom = panel.getBoundingClientRect().bottom + window.scrollY;"
    " window.scrollTo({ top: Math.max(0, Math.round(bottom - window.innerHeight + margin)), behavior: 'instant' });"
    " }"
)


@dataclass(frozen=True)
class AssistantScenePlan:
    """When each step of the widget scene starts, in seconds from the scene's start."""

    example_at: float
    booking_at: float | None


@dataclass
class AssistantSceneProgress:
    """The steps already played in one capture."""

    has_played_example: bool = False
    has_opened_booking: bool = False


class AssistantWidgetScene:
    """The widget scene: its framing, its timeline and its steps."""

    @staticmethod
    def plan(middle_seconds: float, widget_seconds: float) -> AssistantScenePlan:
        """
        Place the steps where the spoken take names them, inside the time the widget scene has.

        Args:
            middle_seconds: The whole middle take, space chapter included (what the prompter paces).
            widget_seconds: The part of it the widget scene fills, before the space chapter.

        Returns:
            The example start, and the booking start or None when the slots would not stay long enough.
        """
        latest_example_start = widget_seconds - EXAMPLE_SECONDS
        example_at = max(_FIRST_BEAT_SECONDS, min(middle_seconds * _EXAMPLE_SHARE, latest_example_start))
        booking_at = max(middle_seconds * _BOOKING_SHARE, example_at + EXAMPLE_SECONDS)
        if booking_at > widget_seconds - _BOOKING_MIN_SECONDS:
            return AssistantScenePlan(example_at=example_at, booking_at=None)
        return AssistantScenePlan(example_at=example_at, booking_at=booking_at)

    @staticmethod
    def frame(page: Any) -> None:
        """
        Show the chat whole: open it when the page draws a launcher, then scroll its lower edge into view.

        Args:
            page: A Playwright (sync) page on the assistant's demo page.

        Raises:
            Exception: when neither the open chat nor its launcher shows up (Playwright timeout).
        """
        if page.query_selector(_PANEL_SELECTOR) is None:
            page.click(_LAUNCHER_SELECTOR, timeout=8000)
        page.wait_for_selector(_PANEL_SELECTOR, timeout=8000)
        page.evaluate(_FRAME_SCRIPT, _FRAME_MARGIN_PX)

    @classmethod
    def play_due_steps(
        cls, page: Any, plan: AssistantScenePlan, elapsed: float, progress: AssistantSceneProgress
    ) -> None:
        """
        Start every step whose time has come, each once.

        Args:
            page: The Playwright (sync) page being captured.
            plan: The scene's timeline.
            elapsed: Seconds since the scene started.
            progress: The steps already played, updated in place.
        """
        if not progress.has_played_example and elapsed >= plan.example_at:
            progress.has_played_example = True
            # A page without the scripted example (an embedded widget) asks its first suggested question instead.
            if not cls._click(page, _EXAMPLE_CHIP_SELECTOR):
                cls._click(page, _FIRST_CHIP_SELECTOR)
        if plan.booking_at is not None and not progress.has_opened_booking and elapsed >= plan.booking_at:
            progress.has_opened_booking = True
            cls._click(page, _APPOINTMENT_CHIP_SELECTOR)

    @classmethod
    def play_in_real_time(cls, page: Any, plan: AssistantScenePlan, started: float, widget_seconds: float) -> None:
        """
        Run the scene against the clock, for a capture that records in real time (the VPS one).

        Args:
            page: The Playwright (sync) page being recorded.
            plan: The scene's timeline.
            started: ``time.monotonic()`` at the scene's start.
            widget_seconds: How long the scene lasts.
        """
        progress = AssistantSceneProgress()
        while (elapsed := time.monotonic() - started) < widget_seconds:
            cls.play_due_steps(page, plan, elapsed, progress)
            page.wait_for_timeout(100)

    @staticmethod
    def _click(page: Any, selector: str) -> bool:
        """
        Click a chip if the page shows it; a missing chip never fails the video.

        Args:
            page: The Playwright (sync) page.
            selector: The chip to click.

        Returns:
            True when the chip was clicked.
        """
        try:
            page.click(selector, timeout=2000)
        except Exception:
            logger.info("Assistant video: %s is not on the page, the scene goes on without it", selector)
            return False
        return True
