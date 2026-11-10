"""Where the receptionist's files live on the core's R2 bucket (its video, thumbnail, photos, documents, portraits)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


class ReceptionistStorage:
    """The receptionist's key prefixes and key builders; the core's ``r2_storage`` stores and serves the files.

    Layout of the receptionist's objects::

        videos/assistant/{slug}.mp4              receptionist prospection video
        images/assistant/{slug}.jpg              receptionist email thumbnail ({vignette_video_assistant})
        images/assistant-photos/{yyyy}/{mm}/{uuid}.jpg   photos visitors send an assistant for a quote (90 days)
        documents/assistant/{assistant_id}/{uuid}.pdf    documents a business gives its assistant (price list, terms…)
        images/assistant-avatars/{assistant_id}/{uuid}.webp   a receptionist's own portrait (photo or logo)
    """

    VIDEOS_ASSISTANT_PREFIX = "videos/assistant"
    IMAGES_ASSISTANT_PREFIX = "images/assistant"
    IMAGES_ASSISTANT_PHOTOS_PREFIX = "images/assistant-photos"
    DOCUMENTS_ASSISTANT_PREFIX = "documents/assistant"
    IMAGES_ASSISTANT_AVATARS_PREFIX = "images/assistant-avatars"

    @classmethod
    def assistant_video_key(cls, slug: str) -> str:
        """Build the key of an assistant's prospection video."""
        return f"{cls.VIDEOS_ASSISTANT_PREFIX}/{slug}.mp4"

    @classmethod
    def assistant_background_key(cls, slug: str) -> str:
        """Build the key of an assistant's video *background* (the recorded widget answering)."""
        return f"{cls.VIDEOS_ASSISTANT_PREFIX}/{slug}-background.mp4"

    @classmethod
    def assistant_thumbnail_key(cls, slug: str) -> str:
        """Build the key of an assistant's email thumbnail."""
        return f"{cls.IMAGES_ASSISTANT_PREFIX}/{slug}.jpg"

    @classmethod
    def assistant_photo_key(cls) -> str:
        """
        Build the key of a photo a visitor sent an assistant, unguessable (its URL is public).

        Returns:
            A unique JPEG object key under the assistant-photos prefix, filed by year and month.
        """
        now = datetime.now(UTC)
        return f"{cls.IMAGES_ASSISTANT_PHOTOS_PREFIX}/{now:%Y/%m}/{uuid.uuid4().hex}.jpg"

    @classmethod
    def assistant_document_key(cls, assistant_id: int) -> str:
        """
        Build the key of a document a business gave its assistant, unguessable (its URL is public).

        Args:
            assistant_id: The assistant it belongs to.

        Returns:
            A unique PDF object key under the assistant-documents prefix, filed by assistant.
        """
        return f"{cls.DOCUMENTS_ASSISTANT_PREFIX}/{assistant_id}/{uuid.uuid4().hex}.pdf"

    @classmethod
    def assistant_avatar_key(cls, assistant_id: int) -> str:
        """
        Build the key of a receptionist's own portrait, new at each upload so no cache serves the previous one.

        Args:
            assistant_id: The assistant it belongs to.

        Returns:
            A unique WebP object key under the assistant-avatars prefix, filed by assistant.
        """
        return f"{cls.IMAGES_ASSISTANT_AVATARS_PREFIX}/{assistant_id}/{uuid.uuid4().hex}.webp"
