"""Enums of the photos a visitor sends through an AI assistant for a quote."""

from enum import Enum


class AiAssistantPhotoUrgency(str, Enum):
    """How urgent the damage on a photo looks to the vision model."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AiAssistantPhotoRejection(str, Enum):
    """Why a photo was refused before any analysis, or could not be stored."""

    TOO_LARGE = "too_large"
    UNREADABLE = "unreadable"
    QUOTA = "quota"
    UNAVAILABLE = "unavailable"
