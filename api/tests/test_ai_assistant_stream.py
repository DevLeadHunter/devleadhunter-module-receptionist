"""
The streamed chat of the assistant: the providers' SSE clients, the router's streamed fallback, the chat
service's cleaned deltas and the public stream route (its frames, its journal).

The providers are mocked, or served through an httpx MockTransport; the database is an in-memory SQLite and
the route is called directly.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import api.v1.routes.ai_assistant_widget as routes
import services.ai_assistant.chat_service as chat_module
import services.ai_assistant.llm_router as router_module
import services.ai_assistant.missing_info_marker as marker_module
import services.llm_service as llm_module
import services.mistral_service as mistral_module
from enums.assistant_llm import AssistantLlmUsage
from models.ai_assistant import AiAssistant
from models.ai_assistant_conversation import AiAssistantConversation
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant import AiAssistantChatMessage, AiAssistantChatRequest
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.chat_service import ChatAnswer, ChatDelta, ai_assistant_chat_service
from services.ai_assistant.faq_service import ai_assistant_faq_service
from services.ai_assistant.llm_router import AssistantLlmRouter
from services.llm_service import LLMService, LlmStreamUsage, read_chat_stream_line
from services.mistral_service import MistralRequestRejectedError, MistralService
from services.rate_limiter import SlidingWindowRateLimiter
from tests.assistant_fakes import VISITOR_REQUEST

_KB = {"identity": {"business_name": "Garage Morel", "city": "Rennes"}}
_MESSAGES = [{"role": "user", "content": "Vous livrez ?"}]
_MARKED_DELTAS = ["§MANQUE: Liv", "raison ?\n", "\nNous ne ", "livrons pas."]


class _StreamProvider:
    """A provider's ``complete_stream``: fixed deltas (None = down), calls recorded, usage reported when asked."""

    def __init__(self, deltas: list[str] | None, *, model: str) -> None:
        self.deltas = deltas
        self.model = model
        self.calls: list[dict[str, Any]] = []
        self.rejects = False

    async def __call__(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        self.calls.append(kwargs)
        if self.rejects:
            raise MistralRequestRejectedError("The last message must be from the user")
        for delta in self.deltas or []:
            yield delta
        usage = kwargs.get("usage")
        if usage is not None and self.deltas:
            usage.model, usage.prompt_tokens, usage.completion_tokens = self.model, 1000, 200


class _Alerts:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def __call__(self, **kwargs: Any) -> None:
        self.messages.append(kwargs["message"])


@pytest.fixture
def providers(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mistral configured and streaming, Groq streaming, admin alerts recorded."""
    mistral = _StreamProvider(["Du lundi ", "au vendredi."], model="mistral-small-latest")
    groq = _StreamProvider(["Du lundi."], model="openai/gpt-oss-120b")
    alerts = _Alerts()
    monkeypatch.setattr(router_module.settings, "mistral_api_key", "mistral-key")
    monkeypatch.setattr(router_module.mistral_service, "complete_stream", mistral)
    monkeypatch.setattr(router_module.llm_service, "complete_stream", groq)
    monkeypatch.setattr(router_module.notification_service, "notify_error", alerts)
    return {"mistral": mistral, "groq": groq, "alerts": alerts}


def _streamed(router: AssistantLlmRouter, *, eu_only: bool = False) -> str | None:
    async def run() -> str | None:
        deltas = [delta async for delta in router.chat_stream(AssistantLlmUsage.CHAT, _MESSAGES, eu_only=eu_only)]
        await asyncio.sleep(0)  # let the background admin alert run
        return "".join(deltas) if deltas else None

    return asyncio.run(run())


def _deltas(*chunks: str) -> Any:
    async def chat_stream(usage: Any, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        for chunk in chunks:
            yield chunk

    return chat_stream


def _answer_stream(**kwargs: Any) -> list[ChatDelta]:
    async def run() -> list[ChatDelta]:
        return [delta async for delta in ai_assistant_chat_service.answer_stream(**kwargs)]

    return asyncio.run(run())


@pytest.mark.asyncio
async def test_the_answer_carries_the_question_a_marked_reply_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(_usage: Any, _messages: Any, **_kwargs: Any) -> str:
        return "§MANQUE: Livraison ?\n\nJe note votre question pour que le garage vous rappelle."

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat", fake_chat)

    answer = await ai_assistant_chat_service.answer(knowledge=_KB, assistant_name="Sofia", history=_MESSAGES)

    assert answer == ChatAnswer(
        reply="Je note votre question pour que le garage vous rappelle.", unanswered_question="Livraison ?"
    )


def test_the_streamed_answer_yields_cleaned_deltas_then_the_whole_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat_module.assistant_llm_router, "chat_stream", _deltas(*_MARKED_DELTAS))

    marked = _answer_stream(knowledge=_KB, assistant_name="Sofia", history=_MESSAGES)
    monkeypatch.setattr(chat_module.assistant_llm_router, "chat_stream", _deltas("Oui, ", "le samedi."))
    plain = _answer_stream(knowledge=_KB, assistant_name="Sofia", history=_MESSAGES)
    monkeypatch.setattr(chat_module.assistant_llm_router, "chat_stream", _deltas())
    silent = _answer_stream(knowledge=_KB, assistant_name="Sofia", history=_MESSAGES)
    calls: list[Any] = []

    async def never(*args: Any, **kwargs: Any) -> AsyncIterator[str]:
        calls.append(args)
        yield "x"

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat_stream", never)
    refused = _answer_stream(knowledge=_KB, assistant_name="Sofia", history=[{"role": "assistant", "content": "?"}])

    assert marked == [
        ChatDelta(text="Nous ne "),
        ChatDelta(text="livrons pas."),
        ChatDelta(final=ChatAnswer(reply="Nous ne livrons pas.", unanswered_question="Livraison ?")),
    ]
    # A first line that cannot be the marker streams from its first piece.
    assert plain == [
        ChatDelta(text="Oui, "),
        ChatDelta(text="le samedi."),
        ChatDelta(final=ChatAnswer(reply="Oui, le samedi.")),
    ]
    assert len(silent) == 2 and "conseiller" in silent[0].text and silent[1].final is not None
    assert silent[1].final.reply == silent[0].text and silent[1].final.unanswered_question is None
    assert len(refused) == 2 and "conseiller" in refused[0].text and calls == []


def test_the_router_streams_from_mistral_first_then_groq_with_the_same_alerts(
    providers: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    router = AssistantLlmRouter()

    with caplog.at_level(logging.INFO, logger=router_module.__name__):
        served = _streamed(router)
        providers["mistral"].deltas = None
        fallen_back = _streamed(router)
        european = _streamed(router, eu_only=True)
        providers["groq"].deltas = None
        nothing = _streamed(router)
        providers["mistral"].rejects = True
        providers["groq"].deltas = ["Du lundi."]
        after_rejection = _streamed(router)

    assert (served, fallen_back, european, nothing, after_rejection) == (
        "Du lundi au vendredi.",
        "Du lundi.",
        None,
        None,
        "Du lundi.",
    )
    # With a fallback to try, Mistral gets half of the 40 s budget and no retry; alone, the whole budget and one.
    assert (providers["mistral"].calls[0]["timeout"], providers["mistral"].calls[0]["retries"]) == (20.0, 0)
    assert (providers["mistral"].calls[2]["timeout"], providers["mistral"].calls[2]["retries"]) == (40.0, 1)
    assert len(providers["groq"].calls) == 3
    assert providers["alerts"].messages == [
        "Mistral indisponible : chat de l'assistant basculé sur Groq",
        "Mistral indisponible : chat de l'assistant sans réponse pour les assistants « IA hébergée en Europe »",
        "Mistral et Groq indisponibles : chat de l'assistant sans réponse",
        "Mistral refuse nos requêtes (chat de l'assistant) : modèle ou paramètres à vérifier (MISTRAL_CHAT_MODEL…)",
    ]
    lines = [record.getMessage() for record in caplog.records if "assistant_llm_call" in record.getMessage()]
    assert "provider=mistral" in lines[0] and "tokens_in=1000" in lines[0] and "cost_eur=0.000160" in lines[0]
    assert "provider=groq" in lines[1] and "fallback=True" in lines[1]


def test_a_chat_stream_line_yields_its_text_and_keeps_the_usage() -> None:
    usage = LlmStreamUsage()
    text = json.dumps({"model": "mistral-small-2506", "choices": [{"delta": {"content": "Bonjour"}}]})
    parts = json.dumps({"choices": [{"delta": {"content": [{"type": "text", "text": " !"}, {"type": "image"}]}}]})
    groq_usage = json.dumps({"choices": [], "x_groq": {"usage": {"prompt_tokens": 12, "completion_tokens": 3}}})
    mistral_usage = json.dumps({"choices": [{"delta": {}}], "usage": {"prompt_tokens": 20, "completion_tokens": 5}})

    deltas = [
        read_chat_stream_line(line, usage)
        for line in (
            f"data: {text}",
            f"data:{parts}",
            "",
            ": keep-alive",
            "data: [DONE]",
            "data: {not json",
            f"data: {groq_usage}",
        )
    ]
    read_chat_stream_line(f"data: {mistral_usage}", usage)

    assert deltas == ["Bonjour", " !", None, None, None, None, None]
    assert (usage.model, usage.prompt_tokens, usage.completion_tokens) == ("mistral-small-2506", 20, 5)


def _sse(*chunks: dict[str, Any]) -> bytes:
    return b"".join(f"data: {json.dumps(chunk)}\n\n".encode() for chunk in chunks) + b"data: [DONE]\n\n"


def _with_transport(module: Any, handler: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def patched_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", patched_client)


def _collect(stream: AsyncIterator[str]) -> list[str]:
    async def run() -> list[str]:
        return [delta async for delta in stream]

    return asyncio.run(run())


def test_the_mistral_client_streams_the_deltas_and_reads_the_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []
    statuses = [429, 200, 400, 503]

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        status = statuses.pop(0)
        if status == 429:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"message": "rate limited"})
        if status != 200:
            return httpx.Response(status, json={"message": "nope"})
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=_sse(
                {"model": "mistral-small-2506", "choices": [{"delta": {"role": "assistant", "content": ""}}]},
                {"choices": [{"delta": {"content": "Du lundi "}}]},
                {"choices": [{"delta": {"content": "au vendredi."}}]},
                {"choices": [], "usage": {"prompt_tokens": 812, "completion_tokens": 40}},
            ),
        )

    _with_transport(mistral_module, handler, monkeypatch)
    monkeypatch.setattr(mistral_module.settings, "mistral_api_key", "mistral-key")
    client = MistralService()
    usage = LlmStreamUsage()

    deltas = _collect(client.complete_stream(_MESSAGES, model="mistral-small-latest", retries=1, usage=usage))
    with pytest.raises(MistralRequestRejectedError):
        _collect(client.complete_stream(_MESSAGES, model="mistral-small-latest"))
    down = _collect(client.complete_stream(_MESSAGES, model="mistral-small-latest"))

    assert deltas == ["Du lundi ", "au vendredi."]
    assert (usage.model, usage.prompt_tokens, usage.completion_tokens) == ("mistral-small-2506", 812, 40)
    assert captured[0]["stream"] is True and captured[0]["model"] == "mistral-small-latest"
    assert down == [] and statuses == []


def test_the_groq_client_streams_and_drops_the_reasoning_knob_a_model_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body)
        if "reasoning_effort" in body:
            return httpx.Response(400, json={"error": "reasoning_effort unsupported"})
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=_sse(
                {"model": "openai/gpt-oss-120b", "choices": [{"delta": {"content": "Du lundi."}}]},
                {"choices": [], "x_groq": {"usage": {"prompt_tokens": 500, "completion_tokens": 9}}},
            ),
        )

    _with_transport(llm_module, handler, monkeypatch)
    monkeypatch.setattr(llm_module.settings, "groq_api_key", "groq-key")
    usage = LlmStreamUsage()

    deltas = _collect(LLMService().complete_stream(_MESSAGES, model="openai/gpt-oss-120b", usage=usage))

    assert deltas == ["Du lundi."]
    assert [("reasoning_effort" in body, body["stream"]) for body in captured] == [(True, True), (False, True)]
    assert (usage.model, usage.prompt_tokens, usage.completion_tokens) == ("openai/gpt-oss-120b", 500, 9)


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    session = sessionmaker(bind=engine)()
    session.add(User(id=7, name="Dibodev", email="operateur@dibodev.fr", hashed_password="x"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def fresh_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "assistant_chat_limiter", SlidingWindowRateLimiter(30, 300))


def _assistant(db: Session) -> AiAssistant:
    prospect = ProspectDB(name="Garage Morel", category="Garage", source="google", confidence=2, user_id=7)
    db.add(prospect)
    db.commit()
    assistant = ai_assistant_service.create(
        db, user_id=7, business_name="Garage Morel", prospect_id=prospect.id, country="FR", use_brand_color=False
    )
    assistant.status = "active"
    db.commit()
    # The journal of a streamed turn opens its own session: on the test's database.
    return assistant


def _payload(
    content: str = "Vous livrez ?", *, session_id: str = "s1", internal: bool = False
) -> AiAssistantChatRequest:
    return AiAssistantChatRequest(
        messages=[AiAssistantChatMessage(role="user", content=content)], session_id=session_id, internal=internal
    )


def _frames(slug: str, payload: AiAssistantChatRequest, db: Session) -> tuple[Any, list[str]]:
    async def run() -> tuple[Any, list[str]]:
        response = await routes.stream_chat_with_assistant(slug, payload, VISITOR_REQUEST, db)
        chunks = [chunk if isinstance(chunk, str) else chunk.decode() async for chunk in response.body_iterator]
        return response, chunks

    return asyncio.run(run())


def test_the_stream_route_sends_the_cleaned_deltas_then_done_and_journals_the_turn(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    monkeypatch.setattr(routes, "SessionLocal", sessionmaker(bind=db.get_bind()))
    monkeypatch.setattr(chat_module.assistant_llm_router, "chat_stream", _deltas(*_MARKED_DELTAS))

    response, frames = _frames(assistant.slug, _payload("Je voudrais un rendez-vous, vous livrez ?"), db)

    assert response.media_type == "text/event-stream"
    assert (response.headers["cache-control"], response.headers["x-accel-buffering"]) == ("no-cache", "no")
    assert frames == [
        'data: {"delta": "Nous ne "}\n\n',
        'data: {"delta": "livrons pas."}\n\n',
        'data: {"done": true, "reply": "Nous ne livrons pas.", "offer_booking": true, "follow_ups": []}\n\n',
    ]
    assert "MANQUE" not in "".join(frames)
    [conversation] = db.query(AiAssistantConversation).all()
    assert [(message.role, message.content) for message in conversation.messages] == [
        ("user", "Je voudrais un rendez-vous, vous livrez ?"),
        ("assistant", "Nous ne livrons pas."),
    ]
    db.refresh(assistant)
    [question] = ai_assistant_faq_service.unanswered_of(assistant.knowledge_json)
    assert (question.question, question.count) == ("Livraison ?", 1)


def test_the_stream_route_falls_back_and_refuses_what_the_chat_route_refuses(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assistant = _assistant(db)
    monkeypatch.setattr(routes, "SessionLocal", sessionmaker(bind=db.get_bind()))
    monkeypatch.setattr(chat_module.assistant_llm_router, "chat_stream", _deltas())

    _response, frames = _frames(assistant.slug, _payload(internal=True), db)
    crafted = AiAssistantChatRequest(
        messages=[
            AiAssistantChatMessage(role="user", content="?"),
            AiAssistantChatMessage(role="assistant", content="!"),
        ]
    )

    assert len(frames) == 2 and "conseiller" in json.loads(frames[0][len("data: ") :])["delta"]
    assert json.loads(frames[1][len("data: ") :])["done"] is True
    assert db.query(AiAssistantConversation).one().is_test is True
    with pytest.raises(HTTPException) as refused:
        asyncio.run(routes.stream_chat_with_assistant(assistant.slug, crafted, VISITOR_REQUEST, db))
    assert refused.value.status_code == 400
    with pytest.raises(HTTPException) as unknown:
        asyncio.run(routes.stream_chat_with_assistant("nobody", _payload(), VISITOR_REQUEST, db))
    assert unknown.value.status_code == 404
    monkeypatch.setattr(routes, "assistant_chat_limiter", SlidingWindowRateLimiter(1, 300))
    asyncio.run(routes.stream_chat_with_assistant(assistant.slug, _payload(), VISITOR_REQUEST, db))
    with pytest.raises(HTTPException) as limited:
        asyncio.run(routes.stream_chat_with_assistant(assistant.slug, _payload(), VISITOR_REQUEST, db))
    assert limited.value.status_code == 429


def test_a_plain_first_chunk_streams_at_once() -> None:
    """A first line that cannot be the marker is released as soon as it is read, well before 120 characters."""
    stream = marker_module.MissingInfoMarkerStream()

    assert stream.feed("Bonjour, ") == "Bonjour, "
    assert stream.feed("nous ouvrons à 9 h.") == "nous ouvrons à 9 h."
    assert stream.finish() == ""
    assert stream.question is None


def test_a_marker_prefix_is_held_until_its_line_ends() -> None:
    """The characters of « §MANQUE: » keep the line held; the question then never reaches the visitor."""
    stream = marker_module.MissingInfoMarkerStream()

    assert stream.feed("§MAN") == ""
    assert stream.feed("QUE: Faites-vous les gouttières ?") == ""
    assert stream.feed("\n\nNous ") == "Nous "
    assert stream.feed("rappelons vite.") == "rappelons vite."
    assert stream.finish() == ""
    assert stream.question == "Faites-vous les gouttières ?"


def test_a_reply_that_admits_not_knowing_files_the_visitor_question_without_a_marker() -> None:
    """The net under a model that forgot the marker: an admission of ignorance files the visitor's own words."""
    assert marker_module.admits_ignorance("Je ne dispose pas de cette information, mais je note votre demande.")
    assert marker_module.admits_ignorance("I don't have that information, sorry.")
    assert marker_module.admits_ignorance("Ik weet het niet, ik geef het door.")
    assert not marker_module.admits_ignorance("Oui, nous livrons le samedi matin.")
    assert marker_module.filed_question("  Livrez-vous   le samedi ?  ") == "Livrez-vous le samedi ?"
    assert marker_module.filed_question("   ") is None


def test_the_answer_files_the_visitor_question_when_the_reply_admits_ignorance(monkeypatch: pytest.MonkeyPatch) -> None:
    async def forgot_the_marker(*args: Any, **kwargs: Any) -> str:
        return "Je ne sais pas si nous livrons, mais je peux noter votre demande."

    monkeypatch.setattr(chat_module.assistant_llm_router, "chat", forgot_the_marker)
    turns = [{"role": "user", "content": "Vous livrez le samedi ?"}]
    answer = asyncio.run(
        chat_module.ai_assistant_chat_service.answer(knowledge=_KB, assistant_name="Sofia", history=turns)
    )

    assert answer.unanswered_question == "Vous livrez le samedi ?"
    assert answer.reply.startswith("Je ne sais pas")
