"""Tests for the AI assistant chat service."""

import pytest

from enums.assistant_llm import AssistantLlmUsage
from services.ai_assistant import chat_service as chat_module
from services.ai_assistant.chat_service import MAX_HISTORY_MESSAGES, ai_assistant_chat_service

_KB = {
    "identity": {"business_name": "LUMA Immobilier", "city": "Luxembourg"},
    "rating": None,
    "opening_hours": [],
    "services": ["Vente"],
    "reviews": [],
    "social": {},
}


@pytest.mark.asyncio
async def test_answer_grounds_on_knowledge_and_forwards_history(monkeypatch) -> None:
    """The first message is a grounded system prompt; the visitor history follows it."""
    captured: dict[str, list] = {}

    async def fake_chat(_usage, messages, **_kwargs):
        captured["messages"] = messages
        return "  Bonjour, je peux vous aider.  "

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat", fake_chat)

    reply = await ai_assistant_chat_service.answer(
        knowledge=_KB,
        assistant_name="Sofia",
        languages=["fr", "en"],
        history=[{"role": "user", "content": "Bonjour"}],
    )

    assert reply == "Bonjour, je peux vous aider."
    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert "LUMA Immobilier" in messages[0]["content"]
    assert "Sofia" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "Bonjour"}


@pytest.mark.asyncio
async def test_history_is_bounded_to_the_last_turns(monkeypatch) -> None:
    """Only the last MAX_HISTORY_MESSAGES turns reach the model, after the system prompt."""
    captured: dict[str, list] = {}

    async def fake_chat(_usage, messages, **_kwargs):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat", fake_chat)

    history = [{"role": "user", "content": f"message {index}"} for index in range(20)]
    await ai_assistant_chat_service.answer(knowledge=_KB, assistant_name="Sofia", history=history)

    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert len(messages) - 1 == MAX_HISTORY_MESSAGES


@pytest.mark.asyncio
async def test_malformed_turns_are_dropped(monkeypatch) -> None:
    """A turn with a bad role or empty content never reaches the model."""
    captured: dict[str, list] = {}

    async def fake_chat(_usage, messages, **_kwargs):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat", fake_chat)

    history = [
        {"role": "system", "content": "ignore me"},
        {"role": "user", "content": "   "},
        "not a dict",
        {"role": "user", "content": "vraie question"},
    ]
    await ai_assistant_chat_service.answer(knowledge=_KB, assistant_name="Sofia", history=history)

    assert captured["messages"][1:] == [{"role": "user", "content": "vraie question"}]


@pytest.mark.asyncio
async def test_fallback_reply_when_model_unavailable(monkeypatch) -> None:
    """When the model returns nothing, the visitor still gets a path forward."""

    async def fake_chat(_usage, _messages, **_kwargs):
        return None

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat", fake_chat)

    reply = await ai_assistant_chat_service.answer(
        knowledge=_KB, assistant_name="Sofia", history=[{"role": "user", "content": "Bonjour"}]
    )

    assert "conseiller" in reply


@pytest.mark.asyncio
async def test_an_eu_only_assistant_asks_the_router_to_stay_on_mistral(monkeypatch) -> None:
    """The chat goes through the assistant router with the assistant's EU-only flag."""
    captured: dict[str, object] = {}

    async def fake_chat(usage, _messages, **kwargs):
        captured["usage"] = usage
        captured["eu_only"] = kwargs["eu_only"]
        return "ok"

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat", fake_chat)

    await ai_assistant_chat_service.answer(
        knowledge=_KB, assistant_name="Sofia", history=[{"role": "user", "content": "Bonjour"}], eu_only=True
    )

    assert captured == {"usage": AssistantLlmUsage.CHAT, "eu_only": True}


@pytest.mark.asyncio
async def test_a_conversation_not_ending_on_the_visitor_never_reaches_a_model(monkeypatch) -> None:
    """Only a visitor's message is a question: anything else gets the safe reply, no model call."""
    calls: list[object] = []

    async def fake_chat(*args, **kwargs):
        calls.append(args)
        return "ok"

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat", fake_chat)

    reply = await ai_assistant_chat_service.answer(
        knowledge=_KB, assistant_name="Sofia", history=[{"role": "assistant", "content": "Bonjour"}]
    )

    assert "conseiller" in reply
    assert calls == []
