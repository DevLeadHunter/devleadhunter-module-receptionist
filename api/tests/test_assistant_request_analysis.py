"""Unit tests for typing and summarizing an assistant request, and for its signed email link.

The model is mocked: these tests pin the contract around it — a valid answer is used, an
off-contract or missing one falls back to keyword rules and the visitor's own words — and the
« marquer traitée » link that the owner clicks from the summary email.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import services.ai_assistant.request_analyzer as analyzer_module
from enums.ai_assistant_request import AiAssistantRequestType
from services.ai_assistant.request_analyzer import AiAssistantRequestAnalyzer, TranscriptLine
from services.ai_assistant.request_links import AiAssistantRequestLinks

_TRANSCRIPT = [
    TranscriptLine(role="user", content="Bonjour, j'ai des tuiles déplacées après la tempête"),
    TranscriptLine(role="assistant", content="Je note. Pouvez-vous me laisser vos coordonnées ?"),
]


def _analyze(monkeypatch: pytest.MonkeyPatch, answer: dict[str, Any] | None, need: str | None = None) -> Any:
    async def fake_complete_json(messages: list[dict[str, Any]], **_: object) -> dict[str, Any] | None:
        fake_complete_json.messages = messages  # type: ignore[attr-defined]
        return answer

    monkeypatch.setattr(analyzer_module.llm_service, "complete_json", fake_complete_json)
    result = asyncio.run(
        AiAssistantRequestAnalyzer().analyze(business_name="Toitures Morel", need=need, transcript=_TRANSCRIPT)
    )
    return result, getattr(fake_complete_json, "messages", None)


def test_a_valid_model_answer_types_and_summarizes_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    result, messages = _analyze(
        monkeypatch, {"type": "quote", "summary": "Tuiles déplacées côté rue, devis de réparation demandé."}
    )

    assert result.type is AiAssistantRequestType.QUOTE
    assert result.summary == "Tuiles déplacées côté rue, devis de réparation demandé."
    assert "Visiteur : Bonjour, j'ai des tuiles déplacées" in messages[1]["content"]
    assert "DONNÉES" in messages[0]["content"]


def test_an_unknown_type_keeps_the_summary_and_falls_back_on_keywords(monkeypatch: pytest.MonkeyPatch) -> None:
    result, _ = _analyze(monkeypatch, {"type": "sales", "summary": "Fuite sous la toiture."}, need="Fuite urgente")

    assert result.type is AiAssistantRequestType.URGENT
    assert result.summary == "Fuite sous la toiture."


def test_no_model_answer_uses_the_visitor_words(monkeypatch: pytest.MonkeyPatch) -> None:
    result, _ = _analyze(monkeypatch, None, need="  Combien pour  refaire une gouttière ? ")

    assert result.type is AiAssistantRequestType.QUOTE
    assert result.summary == "Combien pour refaire une gouttière ?"


def test_a_failing_model_never_loses_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken(*_: object, **__: object) -> None:
        raise RuntimeError("groq down")

    monkeypatch.setattr(analyzer_module.llm_service, "complete_json", broken)

    result = asyncio.run(AiAssistantRequestAnalyzer().analyze(business_name="X", need="Un rdv lundi ?", transcript=[]))

    assert result.type is AiAssistantRequestType.APPOINTMENT


@pytest.mark.parametrize(
    ("need", "expected"),
    [
        ("Il y a une fuite dans la cuisine", AiAssistantRequestType.URGENT),
        ("Je voudrais un rendez-vous pour un contrôle", AiAssistantRequestType.APPOINTMENT),
        ("Quel est votre tarif pour un débroussaillage", AiAssistantRequestType.QUOTE),
        ("Vous travaillez le samedi ?", AiAssistantRequestType.QUESTION),
        ("Merci", AiAssistantRequestType.OTHER),
    ],
)
def test_keyword_rules_type_the_request(need: str, expected: AiAssistantRequestType) -> None:
    assert AiAssistantRequestAnalyzer().fallback(need=need, transcript=[]).type is expected


def test_the_transcript_is_bounded_to_the_latest_turns() -> None:
    long_transcript = [TranscriptLine(role="user", content="x" * 900) for _ in range(20)]

    bounded = AiAssistantRequestAnalyzer.bound_transcript(long_transcript)

    assert len(bounded) == AiAssistantRequestAnalyzer.TRANSCRIPT_MAX_LINES
    assert all(len(line.content) == AiAssistantRequestAnalyzer.TRANSCRIPT_LINE_MAX_CHARS for line in bounded)


def test_the_handled_link_verifies_only_for_its_request_until_it_expires() -> None:
    now = datetime(2026, 9, 24, 12, tzinfo=UTC)
    url = AiAssistantRequestLinks.handled_url(42, now=now)
    expires_at = int(url.split("exp=")[1].split("&")[0])
    token = url.split("token=")[1]

    assert "/api/v1/ai-assistants/public/requests/42/handled?" in url
    assert AiAssistantRequestLinks.verify(42, expires_at, token, now=now)
    assert not AiAssistantRequestLinks.verify(43, expires_at, token, now=now)
    assert not AiAssistantRequestLinks.verify(42, expires_at + 1, token, now=now)
    assert not AiAssistantRequestLinks.verify(42, expires_at, None, now=now)
    assert not AiAssistantRequestLinks.verify(42, expires_at, token, now=now + timedelta(days=31))
