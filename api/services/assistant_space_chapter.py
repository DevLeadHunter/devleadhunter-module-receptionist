"""
The last chapter of the assistant video: the example client space, where what the receptionist collects lands.

The video's middle segment shows the widget answering; when the presenter clip leaves enough time, its last
seconds switch to the example space (``/client/exemple``) and scroll gently down to the requests card, the way
the site video ends on the editor. Both captures share this script: the VPS one (Playwright's own recording,
real time) and the desktop one (frame by frame), so the two videos tell the same story.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

from services.video_pipeline import MIN_SCROLL_SECONDS

# How long the chapter lasts, and the shortest widget scene it may follow.
CHAPTER_SECONDS = 7.0
# Inside the chapter: a beat on the top of the space, a gentle scroll to the requests, then a hold.
_HOLD_BEFORE_SCROLL = 0.17
_SCROLL_UNTIL = 0.6
# Where the requests card lands under the top of the viewport: the « N demandes à traiter » title stays in view.
_CARD_TOP_MARGIN_PX = 100
# The example banner is for the visitor, not for the video.
_HIDE_BANNER_CSS = ".cs__example{display:none !important}"


class AssistantSpaceChapter:
    """The example-space chapter: its timing, its page, its scroll."""

    @staticmethod
    def seconds_for(total_seconds: float) -> float:
        """
        How long the chapter lasts inside a middle segment.

        Args:
            total_seconds: The whole middle segment (the presenter clip without its intro and outro).

        Returns:
            ``CHAPTER_SECONDS`` when the widget scene keeps at least its minimum, else 0 (no chapter).
        """
        return CHAPTER_SECONDS if total_seconds >= MIN_SCROLL_SECONDS + CHAPTER_SECONDS else 0.0

    @staticmethod
    def url_for(demo_url: str) -> str:
        """
        The example space to show after an assistant's demo page.

        Args:
            demo_url: The assistant's demo page (``…/ia/{slug}``, with or without a query).

        Returns:
            ``…/client/exemple?demo={slug}`` on the same host (the banner's way back to the demo).
        """
        parts = urlparse(demo_url)
        slug = parts.path.rstrip("/").rsplit("/", 1)[-1]
        return urlunparse(parts._replace(path="/client/exemple", query=f"demo={slug}", fragment=""))

    @staticmethod
    def scroll_position(progress: float, target: int) -> int:
        """
        Where the page is scrolled at a point of the chapter.

        Args:
            progress: The position inside the chapter, from 0 to 1.
            target: The scroll that puts the requests card under the top of the viewport.

        Returns:
            0 during the first beat, an eased scroll up to ``target`` until 60 %, ``target`` after.
        """
        if progress <= _HOLD_BEFORE_SCROLL:
            return 0
        if progress >= _SCROLL_UNTIL:
            return target
        ratio = (progress - _HOLD_BEFORE_SCROLL) / (_SCROLL_UNTIL - _HOLD_BEFORE_SCROLL)
        eased = 4 * ratio**3 if ratio < 0.5 else 1 - ((-2 * ratio + 2) ** 3) / 2
        return round(target * eased)

    @staticmethod
    def open(page: Any, url: str) -> int:
        """
        Load the example space in the page being recorded, at its top, ready to scroll.

        Args:
            page: A Playwright (sync) page.
            url: The example space URL.

        Returns:
            The scroll that puts the requests card under the top of the viewport.
        """
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception:
            page.goto(url, wait_until="load", timeout=30000)
        page.wait_for_selector(".csr__list", timeout=15000)
        page.add_style_tag(content=_HIDE_BANNER_CSS)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        target = page.evaluate(
            "() => { const list = document.querySelector('.csr__list'); const card = list && list.closest('section');"
            f" return card ? Math.max(0, Math.round(card.getBoundingClientRect().top + window.scrollY - {_CARD_TOP_MARGIN_PX})) : 0; }}"
        )
        return int(target or 0)

    @classmethod
    def play(cls, page: Any, target: int, seconds: float, *, step_ms: int = 40) -> None:
        """
        Scroll the space in real time, for the VPS recording.

        Args:
            page: The Playwright (sync) page showing the space.
            target: The scroll that puts the requests card under the top of the viewport.
            seconds: How long the chapter lasts.
            step_ms: The pause between two scroll steps.
        """
        steps = max(1, int(seconds * 1000 / step_ms))
        for index in range(steps + 1):
            position = cls.scroll_position(index / steps, target)
            page.evaluate(f"window.scrollTo(0, {position})")
            page.wait_for_timeout(step_ms)
