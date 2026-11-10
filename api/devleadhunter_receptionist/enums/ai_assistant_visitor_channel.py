"""How a visitor hears back about the appointment they booked."""

from enum import Enum


class AiAssistantVisitorChannel(str, Enum):
    """By SMS (a mobile of the served countries) or by email."""

    SMS = "sms"
    EMAIL = "email"
