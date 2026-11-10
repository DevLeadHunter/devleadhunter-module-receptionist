"""The dressing of a receptionist email: its button, its offer table, and not a word lost.

The layout works on the rendered body, so these tests render the receptionist's library templates the way a send
does and check what the prospect receives.
"""

from __future__ import annotations

import re

import pytest

from devleadhunter_receptionist.email_templates import RECEPTIONIST_EMAIL_TEMPLATES
from devleadhunter_receptionist.offer import (
    ASSISTANT_LINK,
    ASSISTANT_VIDEO_LINK,
    ASSISTANT_VIDEO_THUMBNAIL,
    PRICE_ASSISTANT,
    RECEPTIONIST,
    RECEPTIONIST_FIRST_NAME,
    VIRTUAL_ASSISTANT,
)
from enums.email_template_layout import EmailTemplateLayout
from services.email_layout import EmailLayout
from services.email_variables import EmailVariables

_DEMO_URL = "https://demo.example/menuiserie-lefort?src=email"
_ASSISTANT_URL = "https://demo.example/ia/menuiserie-lefort?src=email"
_VIDEO_URL = "https://demo.example/v/menuiserie-lefort?src=email"
_ASSISTANT_VIDEO_URL = "https://demo.example/va/menuiserie-lefort?src=email"
_SIGNATURE = (
    '<div style="margin-top:16px;"><!--StartFragment--><table><tr><td>Léo Guillaume</td></tr></table><br></div>'
)
_CARD_TABLE = EmailTemplateLayout.CARD_TABLE.value
_CARD = EmailTemplateLayout.CARD.value


def _variables() -> dict[str, str]:
    """The substitution map of a send, with the links and thumbnails in the form the variables are built."""
    return {
        EmailVariables.SALUTATION: "Bonjour",
        EmailVariables.COMPANY: "Menuiserie Lefort",
        EmailVariables.CITY: "Rennes",
        EmailVariables.TRADE: "menuisier",
        EmailVariables.OLD_WEBSITE: "menuiserie-lefort.example",
        EmailVariables.DEMO_LINK: EmailVariables.build_demo_link_html(_DEMO_URL),
        ASSISTANT_LINK: EmailVariables.build_demo_link_html(_ASSISTANT_URL),
        RECEPTIONIST_FIRST_NAME: "Léa",
        RECEPTIONIST: "une réceptionniste",
        VIRTUAL_ASSISTANT: "une assistante virtuelle",
        EmailVariables.VIDEO_LINK: _VIDEO_URL,
        EmailVariables.VIDEO_THUMBNAIL: EmailVariables.build_video_thumbnail_html(
            _VIDEO_URL, "https://cdn.example/t.jpg"
        ),
        ASSISTANT_VIDEO_LINK: _ASSISTANT_VIDEO_URL,
        ASSISTANT_VIDEO_THUMBNAIL: EmailVariables.build_video_thumbnail_html(
            _ASSISTANT_VIDEO_URL, "https://cdn.example/ta.jpg", "Votre réceptionniste en vidéo"
        ),
        EmailVariables.PRICE: "500 €",
        PRICE_ASSISTANT: "29 €",
        EmailVariables.EXPIRY_DATE: "2 novembre",
    }


def _rendered(body_html: str, variables: dict[str, str]) -> str:
    for key, value in variables.items():
        body_html = body_html.replace(f"{{{key}}}", value)
    return body_html


def _library_body(name: str) -> str:
    return next(str(template["body_html"]) for template in RECEPTIONIST_EMAIL_TEMPLATES if template["name"] == name)


def _dressed(name: str, layout: str = _CARD_TABLE) -> str:
    variables = _variables()
    return EmailLayout.dress(layout, _rendered(_library_body(name), variables), _SIGNATURE, variables, "#6f5fe0")


def _row_labels(html: str) -> list[str]:
    return re.findall(r'class="em-label"[^>]*><div>([^<]+)</div>', html)


def _letters(html: str) -> str:
    """The text of a fragment without its tags nor its spaces: what must survive the dressing, in order."""
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", html))


def test_a_price_written_before_the_link_keeps_the_email_as_text() -> None:
    html = _dressed("Réceptionniste IA - le prix, sans détour")
    assert _row_labels(html) == []
    assert '<strong style="font-weight:600;color:#141414;">29 €</strong>' in html
    assert ">Parler à Léa</a>" in html


def test_the_table_starts_after_the_last_demo_link() -> None:
    html = _dressed("Réceptionniste IA - le soir, personne ne répond")
    assert _row_labels(html) == ["Prix", "Date", "Réponse"]
    button_at = html.index(">Parler à Léa</a>")
    thumbnail_at = html.index("<img ")
    table_at = html.index("L'essentiel")
    assert button_at < thumbnail_at < table_at


@pytest.mark.parametrize("layout", [_CARD, _CARD_TABLE])
@pytest.mark.parametrize("template", RECEPTIONIST_EMAIL_TEMPLATES, ids=lambda template: str(template["name"]))
def test_no_receptionist_template_loses_a_word(template: dict[str, object], layout: str) -> None:
    variables = _variables()
    body = _rendered(str(template["body_html"]), variables)
    dressed_letters = _letters(EmailLayout.dress(layout, body, "", variables))
    position = 0
    for paragraph in re.findall(r"<(?:p|li)[^>]*>(.*?)</(?:p|li)>", body, re.DOTALL):
        letters = _letters(paragraph)
        found_at = dressed_letters.find(letters, position)
        assert found_at != -1, paragraph
        position = found_at + len(letters)
