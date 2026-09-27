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


class AiAssistantRequestOutcome(str, Enum):
    """What became of a request the owner called back: a client won, or not."""

    WON = "won"
    LOST = "lost"


class AiAssistantRequestChannel(str, Enum):
    """Where the request came in."""

    SITE = "site"
    EMAIL = "email"
    PHOTO = "photo"


class AiAssistantDayPeriod(str, Enum):
    """A half-day a visitor wishes an appointment in (no agenda connected: the business confirms one)."""

    MORNING = "morning"
    AFTERNOON = "afternoon"
