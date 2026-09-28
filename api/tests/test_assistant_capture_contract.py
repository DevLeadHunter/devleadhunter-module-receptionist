"""The receptionist video films the demo host through its ``data-capture`` hooks, and still through the old classes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

import pytest

from services.assistant_space_chapter import AssistantSpaceChapter
from services.assistant_widget_scene import AssistantScenePlan, AssistantSceneProgress, AssistantWidgetScene

_GREETING = '<div class="ai-m ai-m--assistant"><div class="ai-m__bubble">Bonjour, je suis Sofia.</div></div>'
_VISITOR_LINE = '<div class="ai-m ai-m--user"><div class="ai-m__bubble">Une fuite sous mon évier.</div></div>'
_RECEPTIONIST_REPLY = '<div class="ai-m ai-m--assistant"><div class="ai-m__bubble">Envoyez-moi une photo.</div></div>'

_HOOKED_CHIPS = (
    '<button data-capture-chip data-capture="example-chip" class="ai-chip ai-chip--example"'
    " onclick=\"clicked.push('example')\">Voir un exemple</button>"
    '<button data-capture-chip class="ai-chip ai-chip--photo" onclick="clicked.push(\'photo\')">Photo</button>'
    '<button data-capture-chip data-capture="appointment-chip" class="ai-chip ai-chip--appointment"'
    " onclick=\"clicked.push('appointment')\">Rendez-vous</button>"
)
_CLASS_ONLY_CHIPS = (
    '<button class="ai-chip ai-chip--example" onclick="clicked.push(\'example\')">Voir un exemple</button>'
    '<button class="ai-chip ai-chip--appointment" onclick="clicked.push(\'appointment\')">Rendez-vous</button>'
)


def _widget_page(messages: str, *, has_capture_hooks: bool, chips: str | None = None) -> str:
    """The demo page's chat, below the fold, with or without the ``data-capture`` hooks."""
    panel_hook = 'data-capture="panel" ' if has_capture_hooks else ""
    chip_buttons = chips if chips is not None else (_HOOKED_CHIPS if has_capture_hooks else _CLASS_ONLY_CHIPS)
    return (
        "<script>window.clicked = [];</script>"
        '<div style="height: 1500px"></div>'
        f'<section {panel_hook}class="ai-panel" style="height: 500px">'
        f'<div class="ai-thread__log">{messages}</div><div class="ai-chips">{chip_buttons}</div>'
        "</section>"
        '<div style="height: 400px"></div>'
    )


def _space_page(*, has_capture_hooks: bool) -> str:
    """The example client space: the banner, the start block, then the latest requests."""
    home_hook = 'data-capture="client-home" ' if has_capture_hooks else ""
    banner_hook = 'data-capture="example-banner" ' if has_capture_hooks else ""
    row_hook = 'data-capture="request-row" ' if has_capture_hooks else ""
    return (
        f'<main {home_hook}class="cs-home">'
        f'<p {banner_hook}class="cs-example" style="height: 80px">Exemple</p>'
        '<div style="height: 900px">Pour démarrer</div>'
        "<h2>Dernières demandes</h2>"
        f'<div id="requests"><a {row_hook}class="cs-row">Claire Martin</a></div>'
        '<div style="height: 1200px"></div>'
        "</main>"
    )


@pytest.fixture(scope="module")
def page() -> Iterator[Any]:
    """A headless Chromium page (skipped where Playwright has no browser to start)."""
    sync_api = pytest.importorskip("playwright.sync_api")
    playwright = sync_api.sync_playwright().start()
    try:
        browser = playwright.chromium.launch(headless=True)
    except Exception as exc:
        playwright.stop()
        pytest.skip(f"Chromium cannot start here: {exc}")
    browser_page = browser.new_page(viewport={"width": 1280, "height": 720})
    yield browser_page
    browser.close()
    playwright.stop()


@pytest.mark.parametrize("has_capture_hooks", [True, False])
def test_the_example_counts_only_once_the_receptionist_has_the_last_word(page: Any, has_capture_hooks: bool) -> None:
    page.set_content(_widget_page(_GREETING, has_capture_hooks=has_capture_hooks))
    assert not AssistantWidgetScene.has_played_example(page)

    page.set_content(_widget_page(_GREETING + _VISITOR_LINE, has_capture_hooks=has_capture_hooks))
    assert not AssistantWidgetScene.has_played_example(page)

    page.set_content(_widget_page(_GREETING + _VISITOR_LINE + _RECEPTIONIST_REPLY, has_capture_hooks=has_capture_hooks))
    assert AssistantWidgetScene.has_played_example(page)


@pytest.mark.parametrize("has_capture_hooks", [True, False])
def test_the_scene_frames_the_chat_then_plays_the_example_and_the_slots(page: Any, has_capture_hooks: bool) -> None:
    page.set_content(_widget_page(_GREETING, has_capture_hooks=has_capture_hooks))

    AssistantWidgetScene.frame(page)
    AssistantWidgetScene.play_due_steps(
        page, AssistantScenePlan(example_at=0.0, booking_at=0.0), 0.0, AssistantSceneProgress()
    )

    panel_bottom = page.evaluate("document.querySelector('.ai-panel').getBoundingClientRect().bottom")
    assert panel_bottom == pytest.approx(720 - 24, abs=1)
    assert page.evaluate("window.clicked") == ["example", "appointment"]


def test_a_page_without_the_example_asks_its_first_chip(page: Any) -> None:
    suggestion_chips = (
        '<button data-capture-chip class="ai-chip" onclick="clicked.push(\'horaires\')">Vos horaires ?</button>'
        '<button data-capture-chip class="ai-chip" onclick="clicked.push(\'tarifs\')">Vos tarifs ?</button>'
    )
    page.set_content(_widget_page(_GREETING, has_capture_hooks=True, chips=suggestion_chips))

    AssistantWidgetScene.play_due_steps(
        page, AssistantScenePlan(example_at=0.0, booking_at=None), 0.0, AssistantSceneProgress()
    )

    assert page.evaluate("window.clicked") == ["horaires"]


@pytest.mark.parametrize("has_capture_hooks", [True, False])
def test_the_space_chapter_hides_the_banner_and_scrolls_to_the_latest_requests(
    page: Any, has_capture_hooks: bool
) -> None:
    space_url = "data:text/html;charset=utf-8," + quote(_space_page(has_capture_hooks=has_capture_hooks))

    target = AssistantSpaceChapter.open(page, space_url)

    assert page.evaluate("getComputedStyle(document.querySelector('.cs-example')).display") == "none"
    requests_top = page.evaluate("document.getElementById('requests').getBoundingClientRect().top + window.scrollY")
    assert target == round(requests_top) - 100
