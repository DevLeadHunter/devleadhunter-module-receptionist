"""Grammatical gender an AI assistant persona speaks in."""

from enum import Enum


class AiAssistantPersonaGender(str, Enum):
    """The gender the assistant's French wording agrees with, in the prompt and in the widget texts."""

    FEMININE = "feminine"
    MASCULINE = "masculine"
