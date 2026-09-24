"""
Model routing of the assistant module: Mistral first, a logged Groq fallback, never for an EU-only assistant.

Both providers and the admin notification are mocked; the Mistral client itself is tested through an
httpx MockTransport.
"""

import asyncio
import json
import logging
from typing import Any

import httpx
import pytest

import services.ai_assistant.llm_router as router_module
import services.mistral_service as mistral_module
from enums.assistant_llm import AssistantLlmUsage
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.llm_router import AssistantLlmRouter
from services.llm_service import LlmCompletion
from services.mistral_service import MistralRequestRejectedError, MistralService

_MESSAGES = [{"role": "user", "content": "Quels sont vos horaires ?"}]


class _Provider:
    """A provider's ``complete``: a fixed answer (None = down), calls recorded."""

    def __init__(self, text: str | None, model: str) -> None:
        self.text = text
        self.model = model
        self.calls: list[dict[str, Any]] = []
        self.rejects = False

    async def __call__(self, messages: list[dict[str, Any]], **kwargs: Any) -> LlmCompletion | None:
        self.calls.append(kwargs)
        if self.rejects:
            raise MistralRequestRejectedError("The last message must be from the user")
        if self.text is None:
            return None
        return LlmCompletion(
            text=self.text,
            model=kwargs.get("model") or self.model,
            prompt_tokens=1000,
            completion_tokens=200,
            latency_ms=420,
        )


class _Alerts:
    """The admin notification: the messages sent."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def __call__(self, **kwargs: Any) -> None:
        self.messages.append(kwargs["message"])


@pytest.fixture
def providers(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mistral configured and answering, Groq answering, admin alerts recorded."""
    mistral = _Provider("Du lundi au vendredi, 8 h - 18 h.", "mistral-small-latest")
    groq = _Provider("Du lundi au vendredi.", "openai/gpt-oss-120b")
    alerts = _Alerts()
    vision_models: list[str | None] = ["qwen/qwen3.6-27b"]
    monkeypatch.setattr(router_module.settings, "mistral_api_key", "mistral-key")
    monkeypatch.setattr(router_module.mistral_service, "complete", mistral)
    monkeypatch.setattr(router_module.llm_service, "complete", groq)
    monkeypatch.setattr(router_module.notification_service, "notify_error", alerts)

    async def vision_model() -> str | None:
        return vision_models[0]

    monkeypatch.setattr(router_module.llm_service, "resolve_vision_model", vision_model)
    return {"mistral": mistral, "groq": groq, "alerts": alerts, "vision_models": vision_models}


def _chat(
    router: AssistantLlmRouter, usage: AssistantLlmUsage = AssistantLlmUsage.CHAT, *, eu_only: bool = False
) -> str | None:
    async def run() -> str | None:
        answer = await router.chat(usage, _MESSAGES, eu_only=eu_only)
        await asyncio.sleep(0)  # let the background admin alert run
        return answer

    return asyncio.run(run())


def test_the_assistant_calls_go_to_mistral_first_and_log_their_cost(
    providers: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger=router_module.__name__):
        answer = _chat(AssistantLlmRouter())

    assert answer == "Du lundi au vendredi, 8 h - 18 h."
    assert providers["mistral"].calls[0]["model"] == "mistral-small-latest"
    # With a fallback to try, Mistral gets half of the 40 s budget and no retry.
    assert (providers["mistral"].calls[0]["timeout"], providers["mistral"].calls[0]["retries"]) == (20.0, 0)
    assert providers["groq"].calls == []
    line = next(record.getMessage() for record in caplog.records if "assistant_llm_call" in record.getMessage())
    assert "provider=mistral" in line
    # 1000 tokens in at 0.1 €/M + 200 out at 0.3 €/M.
    assert "cost_eur=0.000160" in line


def test_a_mistral_outage_falls_back_to_groq_with_one_admin_alert(
    providers: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    providers["mistral"].text = None
    router = AssistantLlmRouter()

    with caplog.at_level(logging.INFO, logger=router_module.__name__):
        first = _chat(router)
        second = _chat(router)

    assert first == second == "Du lundi au vendredi."
    assert len(providers["groq"].calls) == 2
    assert providers["alerts"].messages == ["Mistral indisponible : chat de l'assistant basculé sur Groq"]
    served = [record.getMessage() for record in caplog.records if "assistant_llm_call" in record.getMessage()]
    assert all("provider=groq" in line and "fallback=True" in line for line in served)


def test_both_providers_down_is_reported_as_such(providers: dict[str, Any]) -> None:
    providers["mistral"].text = None
    providers["groq"].text = None

    assert _chat(AssistantLlmRouter()) is None
    assert providers["alerts"].messages == ["Mistral et Groq indisponibles : chat de l'assistant sans réponse"]


@pytest.mark.parametrize("usage", list(AssistantLlmUsage))
def test_an_eu_only_assistant_never_reaches_groq(providers: dict[str, Any], usage: AssistantLlmUsage) -> None:
    router = AssistantLlmRouter()

    served = _chat(router, usage, eu_only=True)
    providers["mistral"].text = None
    down = _chat(router, usage, eu_only=True)

    assert served == "Du lundi au vendredi, 8 h - 18 h."
    assert down is None
    assert providers["groq"].calls == []
    # Nothing else can answer an EU-only call: the whole budget and one quick retry.
    assert (providers["mistral"].calls[0]["timeout"], providers["mistral"].calls[0]["retries"]) == (40.0, 1)
    assert len(providers["alerts"].messages) == 1
    assert "EU only" in providers["alerts"].messages[0]


def test_eu_only_and_fallback_outages_are_both_reported(providers: dict[str, Any]) -> None:
    providers["mistral"].text = None
    router = AssistantLlmRouter()

    _chat(router, eu_only=True)
    _chat(router)

    assert len(providers["alerts"].messages) == 2
    assert "EU only" in providers["alerts"].messages[0]
    assert "basculé sur Groq" in providers["alerts"].messages[1]


def test_a_request_mistral_rejects_is_not_an_outage(providers: dict[str, Any]) -> None:
    providers["mistral"].rejects = True

    assert _chat(AssistantLlmRouter()) == "Du lundi au vendredi."
    assert _chat(AssistantLlmRouter(), eu_only=True) is None
    assert providers["alerts"].messages == []


def test_without_a_mistral_key_the_calls_stay_on_groq_except_for_eu_only(
    providers: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(router_module.settings, "mistral_api_key", None)
    router = AssistantLlmRouter()

    assert _chat(router) == "Du lundi au vendredi."
    assert _chat(router, eu_only=True) is None
    assert providers["mistral"].calls == []
    assert len(providers["groq"].calls) == 1
    assert providers["alerts"].messages == [
        "Assistant « EU only » sans clé Mistral (MISTRAL_API_KEY) : chat de l'assistant sans réponse"
    ]


def test_the_photos_use_the_vision_models_of_each_provider(providers: dict[str, Any]) -> None:
    router = AssistantLlmRouter()
    providers["mistral"].text = '{"relevant": true}'

    served = asyncio.run(router.complete_json(AssistantLlmUsage.VISION, _MESSAGES, eu_only=False))
    providers["mistral"].text = None
    providers["groq"].text = '{"relevant": false}'
    fallback = asyncio.run(router.complete_json(AssistantLlmUsage.VISION, _MESSAGES, eu_only=False))
    providers["vision_models"][0] = None
    no_vision_model = asyncio.run(router.complete_json(AssistantLlmUsage.VISION, _MESSAGES, eu_only=False))

    assert served == {"relevant": True} and fallback == {"relevant": False} and no_vision_model is None
    assert providers["mistral"].calls[0]["json_mode"] is True
    assert [call["model"] for call in providers["groq"].calls] == ["qwen/qwen3.6-27b"]


def test_eu_only_cannot_be_turned_on_without_a_mistral_key(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Assistant:
        eu_only: bool | None = None

    monkeypatch.setattr(router_module.settings, "mistral_api_key", None)

    with pytest.raises(ValueError, match="EU only"):
        ai_assistant_service.update(None, _Assistant(), {"eu_only": True})  # type: ignore[arg-type]


def _mistral_with(handler: Any, monkeypatch: pytest.MonkeyPatch) -> MistralService:
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(mistral_module.httpx, "AsyncClient", patched_client)
    monkeypatch.setattr(mistral_module.settings, "mistral_api_key", "mistral-key")
    return MistralService()


def test_the_mistral_client_sends_json_mode_and_reads_text_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "mistral-small-2506",
                "choices": [{"message": {"content": [{"type": "text", "text": '{"type": "quote"}'}]}}],
                "usage": {"prompt_tokens": 812, "completion_tokens": 40},
            },
        )

    completion = asyncio.run(
        _mistral_with(handler, monkeypatch).complete(_MESSAGES, model="mistral-small-latest", json_mode=True)
    )

    assert completion is not None
    assert completion.text == '{"type": "quote"}'
    assert (completion.model, completion.prompt_tokens, completion.completion_tokens) == ("mistral-small-2506", 812, 40)
    assert captured["auth"] == "Bearer mistral-key"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert "reasoning_effort" not in captured["body"]


def test_the_mistral_client_retries_a_rate_limit_only_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = [429, 200, 429]

    def handler(request: httpx.Request) -> httpx.Response:
        status = statuses.pop(0)
        if status == 429:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"message": "rate limited"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}})

    client = _mistral_with(handler, monkeypatch)
    retried = asyncio.run(client.complete(_MESSAGES, model="mistral-small-latest", retries=1))
    single = asyncio.run(client.complete(_MESSAGES, model="mistral-small-latest"))

    assert retried is not None and retried.text == "ok"
    assert single is None


def test_a_malformed_request_is_raised_and_an_outage_is_no_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = [400, 503]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(statuses.pop(0), json={"message": "nope"})

    client = _mistral_with(handler, monkeypatch)

    with pytest.raises(MistralRequestRejectedError):
        asyncio.run(client.complete(_MESSAGES, model="mistral-small-latest"))
    assert asyncio.run(client.complete(_MESSAGES, model="mistral-small-latest")) is None
