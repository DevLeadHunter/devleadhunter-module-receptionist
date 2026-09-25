"""
Model routing of the AI assistant module: Mistral first, Groq as a logged fallback.

The visitors' conversations, their quote photos and the analysis of their requests go to Mistral
(La Plateforme). When Mistral is down the call falls back to Groq, with a warning in the log and an
admin notification sent in the background (at most one per usage and kind of outage every 30
minutes) — never silently. An assistant flagged « EU only » never falls back: its call returns None
and the caller keeps its own safe answer. Each served call logs its provider, model, total latency,
tokens and estimated cost.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from core.config import settings
from enums.assistant_llm import AssistantLlmOutage, AssistantLlmUsage, LlmProvider
from services.llm_service import LlmCompletion, llm_service
from services.mistral_service import MistralRequestRejectedError, mistral_service
from services.notification_service import notification_service

logger = logging.getLogger(__name__)

FALLBACK_ALERT_INTERVAL_SECONDS = 1800.0
# With a fallback to try, Mistral gets half of the caller's time budget, never less than this.
MIN_PROVIDER_TIMEOUT_SECONDS = 10.0
_USAGE_LABELS: dict[AssistantLlmUsage, str] = {
    AssistantLlmUsage.CHAT: "chat de l'assistant",
    AssistantLlmUsage.VISION: "photos de devis",
    AssistantLlmUsage.REQUEST: "analyse des demandes",
    AssistantLlmUsage.REPORT: "rapport mensuel",
}
_OUTAGE_MESSAGES: dict[AssistantLlmOutage, str] = {
    AssistantLlmOutage.FALLBACK: "Mistral indisponible : {usage} basculé sur Groq",
    AssistantLlmOutage.NO_ANSWER: "Mistral et Groq indisponibles : {usage} sans réponse",
    AssistantLlmOutage.EU_ONLY_NO_ANSWER: "Mistral indisponible : {usage} sans réponse pour les assistants « IA hébergée en Europe »",
    AssistantLlmOutage.EU_ONLY_NO_KEY: "Assistant « IA hébergée en Europe » sans clé Mistral (MISTRAL_API_KEY) : {usage} sans réponse",
    AssistantLlmOutage.REJECTED: "Mistral refuse nos requêtes ({usage}) : modèle ou paramètres à vérifier (MISTRAL_CHAT_MODEL…)",
}


def estimate_cost_eur(provider: LlmProvider, completion: LlmCompletion) -> float:
    """
    Estimated cost of a call, from the configured prices per million tokens.

    The prices are those of the provider's chat model: a photo read by another model is an estimate.

    Args:
        provider: Who answered.
        completion: The answer and its token counts.

    Returns:
        The cost in euros (0 when the provider reported no usage).
    """
    if provider is LlmProvider.MISTRAL:
        price_in, price_out = settings.mistral_eur_per_mtok_in, settings.mistral_eur_per_mtok_out
    else:
        price_in, price_out = settings.groq_eur_per_mtok_in, settings.groq_eur_per_mtok_out
    return ((completion.prompt_tokens or 0) * price_in + (completion.completion_tokens or 0) * price_out) / 1_000_000


class AssistantLlmRouter:
    """Sends the assistant module's model calls to Mistral, falling back to Groq unless the assistant is EU only."""

    def __init__(self) -> None:
        # Last admin alert per usage and kind of outage (monotonic seconds): an outage never floods them.
        self._last_alert: dict[tuple[AssistantLlmUsage, AssistantLlmOutage], float] = {}
        # Strong references to the alerts sent in the background (a task nobody holds can be collected).
        self._alert_tasks: set[asyncio.Task[None]] = set()

    async def chat(
        self,
        usage: AssistantLlmUsage,
        messages: list[dict[str, Any]],
        *,
        eu_only: bool,
        max_tokens: int = 500,
        temperature: float = 0.5,
        timeout: float = 40.0,
    ) -> str | None:
        """
        A plain completion for the assistant module.

        Args:
            usage: What the call is for.
            messages: OpenAI-style messages.
            eu_only: The assistant forbids any provider outside Mistral.
            max_tokens: Answer budget.
            temperature: Sampling temperature.
            timeout: Time budget in seconds, shared by Mistral and the fallback.

        Returns:
            The answer text, or None when no allowed provider answered.
        """
        completion = await self.complete(
            usage,
            messages,
            eu_only=eu_only,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=False,
            timeout=timeout,
        )
        return completion.text if completion else None

    async def complete_json(
        self,
        usage: AssistantLlmUsage,
        messages: list[dict[str, Any]],
        *,
        eu_only: bool,
        max_tokens: int = 900,
        temperature: float = 0.2,
        timeout: float = 60.0,
    ) -> dict[str, Any] | None:
        """
        A JSON-mode completion for the assistant module, parsed into a dict.

        Args:
            usage: What the call is for.
            messages: OpenAI-style messages (image parts allowed for the vision usage).
            eu_only: The assistant forbids any provider outside Mistral.
            max_tokens: Answer budget.
            temperature: Sampling temperature.
            timeout: Time budget in seconds, shared by Mistral and the fallback.

        Returns:
            The JSON object, or None when no allowed provider answered one.
        """
        completion = await self.complete(
            usage,
            messages,
            eu_only=eu_only,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=True,
            timeout=timeout,
        )
        return llm_service.parse_json_object(completion.text) if completion else None

    async def complete(
        self,
        usage: AssistantLlmUsage,
        messages: list[dict[str, Any]],
        *,
        eu_only: bool,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
        timeout: float,
    ) -> LlmCompletion | None:
        """
        Route one call: Mistral, then Groq unless the assistant is EU only.

        With a fallback to try, Mistral gets half of the time budget and no retry; an EU-only call gets
        the whole budget and one quick retry, since nothing else can answer it.

        Args:
            usage: What the call is for.
            messages: OpenAI-style messages.
            eu_only: The assistant forbids any provider outside Mistral.
            max_tokens: Answer budget.
            temperature: Sampling temperature.
            json_mode: Ask for a JSON object answer.
            timeout: Time budget in seconds, shared by both providers.

        Returns:
            The completion of the provider that answered, or None.
        """
        started = time.monotonic()
        options: dict[str, Any] = {"max_tokens": max_tokens, "temperature": temperature, "json_mode": json_mode}
        if not mistral_service.is_configured:
            if eu_only:
                self._alert(usage, AssistantLlmOutage.EU_ONLY_NO_KEY)
                return None
            return await self._groq(usage, messages, started=started, fallback=False, timeout=timeout, **options)
        rejected = False
        try:
            completion = await mistral_service.complete(
                messages,
                model=self._mistral_model(usage),
                timeout=timeout if eu_only else max(timeout / 2, MIN_PROVIDER_TIMEOUT_SECONDS),
                retries=1 if eu_only else 0,
                **options,
            )
        except MistralRequestRejectedError:
            # Our request is at fault, not Mistral: the visitor still gets an answer, the admins no alert.
            completion = None
            rejected = True
        if completion is not None:
            self._log(usage, LlmProvider.MISTRAL, completion, started=started, eu_only=eu_only, fallback=False)
            return completion
        if rejected:
            # A refused request is ours to fix (a wrong model name, a bad parameter): the admins hear it once.
            self._alert(usage, AssistantLlmOutage.REJECTED)
        if eu_only:
            if not rejected:
                self._alert(usage, AssistantLlmOutage.EU_ONLY_NO_ANSWER)
            return None
        remaining = max(timeout - (time.monotonic() - started), MIN_PROVIDER_TIMEOUT_SECONDS)
        completion = await self._groq(usage, messages, started=started, fallback=True, timeout=remaining, **options)
        if not rejected:
            self._alert(usage, AssistantLlmOutage.FALLBACK if completion else AssistantLlmOutage.NO_ANSWER)
        return completion

    async def _groq(
        self,
        usage: AssistantLlmUsage,
        messages: list[dict[str, Any]],
        *,
        started: float,
        fallback: bool,
        timeout: float,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> LlmCompletion | None:
        """Ask Groq (its checked vision model for the photos; none available means no answer)."""
        model = await llm_service.resolve_vision_model() if usage is AssistantLlmUsage.VISION else None
        if usage is AssistantLlmUsage.VISION and model is None:
            return None
        completion = await llm_service.complete(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
            timeout=timeout,
        )
        if completion is not None:
            self._log(usage, LlmProvider.GROQ, completion, started=started, eu_only=False, fallback=fallback)
        return completion

    @staticmethod
    def _mistral_model(usage: AssistantLlmUsage) -> str:
        """The Mistral model of a usage (the multimodal one for the photos)."""
        return settings.mistral_vision_model if usage is AssistantLlmUsage.VISION else settings.mistral_chat_model

    def _alert(self, usage: AssistantLlmUsage, outage: AssistantLlmOutage) -> None:
        """Warn in the log, and the admins in the background at most once per interval, of an outage."""
        message = _OUTAGE_MESSAGES[outage].format(usage=_USAGE_LABELS[usage])
        logger.warning("Assistant model outage (%s, %s): %s", usage.value, outage.value, message)
        now = time.monotonic()
        last = self._last_alert.get((usage, outage))
        if last is not None and now - last < FALLBACK_ALERT_INTERVAL_SECONDS:
            return
        self._last_alert[(usage, outage)] = now
        task = asyncio.create_task(self._notify_admins(message, tag=f"assistant-llm-{outage.value}-{usage.value}"))
        self._alert_tasks.add(task)
        task.add_done_callback(self._alert_tasks.discard)

    @staticmethod
    async def _notify_admins(message: str, *, tag: str) -> None:
        """Send the outage notification to the admins; never raises."""
        try:
            await notification_service.notify_error(context="Assistant IA", message=message, tag=tag)
        except Exception:
            logger.warning("Assistant model outage alert could not be sent", exc_info=True)

    @staticmethod
    def _log(
        usage: AssistantLlmUsage,
        provider: LlmProvider,
        completion: LlmCompletion,
        *,
        started: float,
        eu_only: bool,
        fallback: bool,
    ) -> None:
        """Log one served call: total latency (a failed Mistral attempt included), tokens, estimated cost."""
        logger.info(
            "assistant_llm_call usage=%s provider=%s model=%s latency_ms=%s tokens_in=%s tokens_out=%s "
            "cost_eur=%.6f fallback=%s eu_only=%s",
            usage.value,
            provider.value,
            completion.model,
            int((time.monotonic() - started) * 1000),
            completion.prompt_tokens or 0,
            completion.completion_tokens or 0,
            estimate_cost_eur(provider, completion),
            fallback,
            eu_only,
        )


assistant_llm_router = AssistantLlmRouter()
