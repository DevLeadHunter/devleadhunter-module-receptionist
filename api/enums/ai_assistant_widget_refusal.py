"""Codes of the refusals the assistant widget reacts to, rather than showing the API's sentence."""

from enum import Enum


class AiAssistantWidgetRefusalCode(str, Enum):
    """Why a visitor's pick was refused: the widget words it in the visitor's language and offers the slots again."""

    SLOT_TAKEN = "slot_taken"
    SLOT_WITHDRAWN = "slot_withdrawn"
