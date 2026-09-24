"""Answer a website visitor as a prospect's grounded AI receptionist.

The reply is grounded strictly on the assistant's knowledge base (built in ``knowledge_builder``):
the system prompt forbids inventing anything, and the model answers in the visitor's language. When
the model is unavailable, a safe fallback keeps the conversation alive instead of failing.
"""

import logging
import re
from typing import Any

from enums.assistant_llm import AssistantLlmUsage
from services.ai_assistant.knowledge_builder import ai_assistant_knowledge_builder
from services.ai_assistant.llm_router import assistant_llm_router
from services.text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 12
MAX_MESSAGE_CHARS = 2000
# The visitor messages that pick the site and document passages when they exceed the prompt's budget: a follow-up
# (« Et combien ça coûte ? ») keeps the subject of the ones before.
QUESTION_MESSAGES = 3

# Shown when the model cannot answer (no key, outage): never leave the visitor without a path forward.
_FALLBACK_REPLY = (
    "Je rencontre un souci technique momentané. Laissez-moi votre nom et un moyen de vous recontacter, "
    "et un conseiller reviendra vers vous rapidement."
)


# Asking for an appointment, in the widget's languages (accent-free, lower case). « termin » alone: the French
# « terminé » folds to « termine ».
_APPOINTMENT_INTENT = re.compile(
    r"\b(rendez[- ]?vous|rdv|creneaux?|reserver|reservation|afspraak|afspraken|reserveren|reservatie|"
    r"termin|terminvereinbarung|reservieren|appointment|appointments|booking|book)\b"
)


class AiAssistantChatService:
    """Turns a visitor's message into a grounded, multilingual reply from the prospect's assistant."""

    @staticmethod
    def asks_for_appointment(message: str) -> bool:
        """
        Whether a visitor's message asks for an appointment (the widget then opens its appointment panel).

        Args:
            message: The visitor's latest message.

        Returns:
            True when it names an appointment, a slot or a booking.
        """
        return _APPOINTMENT_INTENT.search(TextNormalizer.fold(message or "")) is not None

    async def answer(
        self,
        *,
        knowledge: dict[str, Any],
        assistant_name: str,
        history: list[dict[str, Any]],
        languages: list[str] | None = None,
        tone: str | None = None,
        eu_only: bool = False,
    ) -> str:
        """Answer the latest visitor message, grounded strictly on ``knowledge``.

        Args:
            knowledge: The assistant's knowledge base (``AiAssistant.knowledge_json``).
            assistant_name: The persona name shown to the visitor.
            history: The conversation so far as ``{"role", "content"}`` turns, ending on the visitor.
            languages: Active language ISO codes; the assistant still replies in the visitor's language.
            tone: Optional persona tone.
            eu_only: The assistant only allows Mistral (no Groq fallback).

        Returns:
            The assistant's reply, or a safe fallback when the model is unavailable.
        """
        turns = self._bounded_history(history)
        # Only a conversation ending on the visitor's message is a question to answer (the models refuse others).
        if not turns or turns[-1]["role"] != "user":
            return _FALLBACK_REPLY
        visitor_messages = [turn["content"] for turn in turns if turn["role"] == "user"]
        question = "\n".join(visitor_messages[-QUESTION_MESSAGES:])
        system_prompt = ai_assistant_knowledge_builder.render_system_prompt(
            knowledge, assistant_name=assistant_name, languages=languages, tone=tone, question=question
        )
        identity = knowledge.get("identity") if isinstance(knowledge.get("identity"), dict) else {}
        business_name = identity.get("business_name") or "?"
        # About 4 characters per token in French: the size the website and the documents give the prompt.
        logger.info(
            "Assistant prompt of %s: %d characters, about %d tokens",
            business_name,
            len(system_prompt),
            len(system_prompt) // 4,
        )
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}, *turns]
        reply = await assistant_llm_router.chat(AssistantLlmUsage.CHAT, messages, eu_only=eu_only)
        return (reply or "").strip() or _FALLBACK_REPLY

    @staticmethod
    def _bounded_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep the last valid turns, dropping malformed ones and capping each message's length."""
        bounded: list[dict[str, Any]] = []
        for turn in (history or [])[-MAX_HISTORY_MESSAGES:]:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            content = turn.get("content")
            if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip():
                continue
            bounded.append({"role": role, "content": content.strip()[:MAX_MESSAGE_CHARS]})
        return bounded


ai_assistant_chat_service = AiAssistantChatService()
