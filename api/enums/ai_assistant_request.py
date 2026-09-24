"""Enums of a structured visitor request captured by an AI assistant."""

from enum import Enum


class AiAssistantRequestType(str, Enum):
    """What the visitor wants — drives the alert rules and the owner's triage."""

    QUESTION = "question"
    QUOTE = "quote"
    APPOINTMENT = "appointment"
    URGENT = "urgent"
    OTHER = "other"


class AiAssistantRequestStatus(str, Enum):
    """Where the owner is with a request."""

    NEW = "new"
    HANDLED = "handled"
    DROPPED = "dropped"


class AiAssistantRequestChannel(str, Enum):
    """Where the request came in."""

    SITE = "site"
    EMAIL = "email"
    PHOTO = "photo"
