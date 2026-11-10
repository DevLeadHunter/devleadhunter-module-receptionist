"""The reasons a visitor's pick of a slot is refused, as codes."""

from enum import Enum


class AiAssistantWidgetRefusalCode(str, Enum):
    """Why a visitor's pick of a slot was refused."""

    SLOT_TAKEN = "slot_taken"
    SLOT_WITHDRAWN = "slot_withdrawn"
