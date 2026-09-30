"""Enums of the model routing of the AI assistant module (Mistral first, Groq as fallback)."""

from enum import Enum


class AiAssistantLlmUsage(str, Enum):
    """What an assistant model call is for — each one is routed to Mistral first."""

    CHAT = "assistant_chat"
    VISION = "assistant_vision"
    REQUEST = "assistant_request"
    REPORT = "assistant_report"
    MAIL_TRIAGE = "assistant_mail_triage"
    MAIL_DRAFT = "assistant_mail_draft"


class LlmProvider(str, Enum):
    """The model provider that answered a call."""

    MISTRAL = "mistral"
    GROQ = "groq"


class AiAssistantLlmOutage(str, Enum):
    """What went wrong when an assistant call could not be served by Mistral (one admin alert each)."""

    FALLBACK = "fallback"
    NO_ANSWER = "no_answer"
    EU_ONLY_NO_ANSWER = "eu_only_no_answer"
    EU_ONLY_NO_KEY = "eu_only_no_key"
    # Mistral refused our request itself (a wrong model name, a bad parameter): not an outage, a configuration to fix.
    REJECTED = "rejected"
