"""The receptionist's gendered words follow its first name: « une assistante virtuelle » for Léa, « un assistant virtuel » for Nathan."""

from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from seeders.email_template_seeder import EMAIL_TEMPLATE_LIBRARY
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.receptionist_wording import ReceptionistWording
from services.email_variables import EmailVariables
from services.sms.templates import find_sms_template, render_sms_template
from services.sms_variables import SmsVariables

_HUGO = SimpleNamespace(slug="garage-martin", assistant_name="Hugo", demo_link_sent_at=None, expires_at=None)


def _prospect(db: Session) -> ProspectDB:
    prospect = ProspectDB(name="Garage Martin", category="Garage automobile", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    return prospect


def _render(text: str, variables: dict[str, str]) -> str:
    for key, value in variables.items():
        text = text.replace(f"{{{key}}}", value)
    return text


def test_a_feminine_first_name_reads_une_assistante_virtuelle() -> None:
    assert ReceptionistWording.virtual_assistant(AiAssistant(assistant_name="Léa")) == "une assistante virtuelle"
    assert ReceptionistWording.receptionist(AiAssistant(assistant_name="Sofia")) == "une réceptionniste"


def test_a_masculine_first_name_reads_un_assistant_virtuel() -> None:
    assert ReceptionistWording.virtual_assistant(AiAssistant(assistant_name="Nathan")) == "un assistant virtuel"
    assert ReceptionistWording.receptionist(AiAssistant(assistant_name="Jean-Pierre")) == "un réceptionniste"


def test_without_an_assistant_the_words_stay_empty() -> None:
    assert ReceptionistWording.virtual_assistant(None) == ""
    assert ReceptionistWording.receptionist(None) == ""


def test_the_email_and_sms_maps_agree_with_the_first_name(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_assistant_service, "get_active_for_prospect", lambda db, *, prospect_id, user_id: _HUGO)
    monkeypatch.setattr(ai_assistant_service, "page_url", lambda slug: "https://demo.dibodev.fr/ia/garage-martin")
    monkeypatch.setattr(EmailVariables, "assistant_video_urls", staticmethod(lambda assistant: ("", "")))

    email = EmailVariables.build_for_prospect(db, _prospect(db), user_id=7)
    sms = SmsVariables.build_for_prospect(db, user_id=7, prospect=_prospect(db), assistant=_HUGO)

    for variables in (email, sms):
        assert variables["receptionniste"] == "un réceptionniste"
        assert variables["assistant_virtuel"] == "un assistant virtuel"


def test_the_frank_receptionist_email_reads_right_for_nathan() -> None:
    template = next(t for t in EMAIL_TEMPLATE_LIBRARY if t["name"] == "Réceptionniste IA - franc")
    variables = {
        "entreprise": "Garage Martin",
        "prenom_receptionniste": "Nathan",
        "receptionniste": "un réceptionniste",
        "assistant_virtuel": "un assistant virtuel",
    }

    assert _render(str(template["subject"]), variables) == "un réceptionniste pour Garage Martin"
    assert "j'ai préparé Nathan pour Garage Martin : un assistant virtuel (IA) qui répond" in _render(
        str(template["body_html"]), variables
    )


def test_a_receptionist_sms_reads_right_for_nathan() -> None:
    template = find_sms_template("assistant-relance")
    assert template is not None

    body = render_sms_template(
        template.body,
        {"salutation": "Bonjour", "prenom_receptionniste": "Nathan", "assistant_virtuel": "un assistant virtuel"},
    )

    assert body.startswith("Bonjour, après mon email, Nathan, un assistant virtuel (IA), répond toujours")
