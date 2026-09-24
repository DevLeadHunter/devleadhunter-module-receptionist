"""The receptionist's signed links keep their wire format: links already sent keep working."""

from datetime import datetime

import pytest

from core.config import settings
from services.ai_assistant.calendar_service import AiAssistantCalendarState
from services.ai_assistant.client_links import AiAssistantClientLinks
from services.ai_assistant.request_links import AiAssistantRequestLinks

_NOW = datetime(2026, 9, 24, 12, 0, 0)


def test_the_three_signed_links_keep_their_wire_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "secret_key", "pinned-secret-for-wire-format")

    assert AiAssistantClientLinks.token(12, now=_NOW) == "12.tneuo0.W_Z49in2NHuiWB3Y"
    assert AiAssistantCalendarState.sign(12, now=_NOW) == "12.1790252100.kXEKHjngCpEoPVGhsorSQw"
    assert AiAssistantRequestLinks.sign(12, 1790000000) == (
        "1954b8e63309e479111eddf27ece10849dc3f0376900b905eb4b056c892efc2c"
    )
    assert AiAssistantCalendarState.read("12.1790252100.kXEKHjngCpEoPVGhsorSQw", now=_NOW) == 12
    assert AiAssistantClientLinks.read("12.tneuo0.W_Z49in2NHuiWB3Y", now=_NOW).assistant_id == 12
