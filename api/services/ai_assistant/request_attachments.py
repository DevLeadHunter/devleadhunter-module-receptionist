"""
What a request carries from its widget session: the conversation journal and the photos sent.

The follow-up reads them to type and summarize the request, the owner's alerts and the dashboard to show it. The
photos also type the request: one with photos asks for a quote, urgent when a photo shows an immediate risk.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from enums.ai_assistant_photo import AiAssistantPhotoUrgency
from enums.ai_assistant_request import AiAssistantRequestType
from models.ai_assistant_message import AiAssistantMessage
from models.ai_assistant_request import AiAssistantRequest
from services.ai_assistant.request_analyzer import TranscriptLine


class AiAssistantRequestAttachments:
    """Reads the conversation and the photos a request came with, and the type its photos give it."""

    @staticmethod
    def transcript(db: Session, request: AiAssistantRequest) -> list[TranscriptLine]:
        """
        The conversation of the request's widget session, oldest first.

        Args:
            db: Active database session.
            request: The request.

        Returns:
            The journaled turns (empty when the visitor wrote nothing before leaving details).
        """
        if request.conversation_id is None:
            return []
        messages = (
            db.query(AiAssistantMessage)
            .filter(AiAssistantMessage.conversation_id == request.conversation_id)
            .order_by(AiAssistantMessage.id)
            .all()
        )
        return [
            TranscriptLine(role=message.role, content=message.content, photo_url=message.photo_url)
            for message in messages
        ]

    @staticmethod
    def photo_urls(request: AiAssistantRequest) -> list[str]:
        """
        Public URLs of the photos attached to a request.

        Args:
            request: The request.

        Returns:
            The photo URLs, in upload order (empty when none).
        """
        return [
            str(photo["url"])
            for photo in (request.photos_json or [])
            if isinstance(photo, dict) and isinstance(photo.get("url"), str)
        ]

    @staticmethod
    def type_with_photos(analyzed: AiAssistantRequestType, request: AiAssistantRequest) -> AiAssistantRequestType:
        """A request with photos asks for a quote — urgent when a photo shows an immediate risk."""
        photos = [entry for entry in (request.photos_json or []) if isinstance(entry, dict)]
        if not photos:
            return analyzed
        if any(entry.get("urgency") == AiAssistantPhotoUrgency.HIGH.value for entry in photos):
            return AiAssistantRequestType.URGENT
        if analyzed in (
            AiAssistantRequestType.QUOTE,
            AiAssistantRequestType.APPOINTMENT,
            AiAssistantRequestType.URGENT,
        ):
            return analyzed
        return AiAssistantRequestType.QUOTE
