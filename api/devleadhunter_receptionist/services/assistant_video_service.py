"""Prospection video generation for AI assistants.

The assistant's video is its own thing (a *different* recording from the site video, per the module
brief): the user's assistant-module presenter clip full-screen for the intro/outro, and in the middle
a screen capture of the demo page's chat **answering** — the scripted example plays (a customer writes,
the receptionist asks for a photo and hands the request over), then the appointment slots open
(:mod:`services.assistant_widget_scene`); when the clip leaves enough time, the last seconds switch to the
example client space, where the requests land (:mod:`services.assistant_space_chapter`). The webcam bubble sits
bottom-right so it never covers the chat. The owner's desktop app films and montages it
(:mod:`services.assistant_widget_clip_service`); everything but the storage namespace and the wording is
shared with the site video in :class:`services.prospection_video_service.ProspectionVideoService`.

The mp4 + jpg go to Cloudflare R2 (``videos/assistant/{slug}.mp4`` / ``images/assistant/{slug}.jpg``); the player
page is the demo host's ``/va/{slug}``.
"""

from __future__ import annotations

import logging
from datetime import datetime

from core.config import settings
from enums.ai_assistant_status import AiAssistantStatus
from enums.demo_video_status import DemoVideoStatus
from models.ai_assistant import AiAssistant
from services.prospection_video_service import ProspectionVideoService
from services.r2_storage_service import r2_storage

logger = logging.getLogger(__name__)

# The presenter clip the assistant video uses (a speech about the assistant, not the site).
ASSISTANT_PRESENTER_MODULE = "ai-assistant"


def video_object_key(slug: str) -> str:
    """R2 key of the assistant's generated video."""
    return r2_storage.assistant_video_key(slug)


def thumbnail_object_key(slug: str) -> str:
    """R2 key of the assistant's email thumbnail."""
    return r2_storage.assistant_thumbnail_key(slug)


def video_page_url(slug: str) -> str:
    """Public player page for the assistant's video."""
    return f"{settings.demo_host_base_url.rstrip('/')}/va/{slug}"


def public_video_file_url(slug: str) -> str:
    """Cloudflare URL the player streams the assistant video from."""
    return r2_storage.public_url(video_object_key(slug))


def public_thumbnail_url(slug: str, generated_at: datetime | None = None) -> str:
    """Cloudflare URL of the assistant email thumbnail (cache-busted by ``generated_at``)."""
    url = r2_storage.public_url(thumbnail_object_key(slug))
    if generated_at is not None:
        url = f"{url}?v={int(generated_at.timestamp())}"
    return url


def has_ready_video(assistant: AiAssistant) -> bool:
    """Whether the assistant has a generated, ready-to-serve video."""
    return assistant.video_status == DemoVideoStatus.READY.value


def delete_files_for_slug(slug: str) -> None:
    """Best-effort R2 cleanup of an assistant's video + thumbnail."""
    try:
        r2_storage.delete_many([video_object_key(slug), thumbnail_object_key(slug)])
    except Exception:
        logger.warning("[AssistantVideo] R2 cleanup failed for slug=%s", slug, exc_info=True)


class AssistantVideoService(ProspectionVideoService[AiAssistant]):
    """The prospection video of a receptionist: what its capture needs (an active receptionist) and its files."""

    subject_model = AiAssistant
    kind = "assistant"
    presenter_module = ASSISTANT_PRESENTER_MODULE
    shown_subject = "la réceptionniste"
    missing_presenter_message = (
        "Aucun clip de présentation pour la réceptionniste. Enregistrez d'abord votre vidéo webcam "
        "« réceptionniste » dans les paramètres."
    )

    def _check_can_generate(self, assistant: AiAssistant) -> None:
        """
        Refuse a receptionist that is not active.

        Args:
            assistant: The receptionist.

        Raises:
            ValueError: with the reason the dashboard shows.
        """
        if assistant.status != AiAssistantStatus.ACTIVE.value:
            raise ValueError("La vidéo ne peut être générée que pour une réceptionniste active.")

    def _video_key(self, slug: str) -> str:
        """
        The R2 key of the receptionist video.

        Args:
            slug: The receptionist's slug.

        Returns:
            The object key.
        """
        return video_object_key(slug)

    def _thumbnail_key(self, slug: str) -> str:
        """
        The R2 key of the receptionist video's email thumbnail.

        Args:
            slug: The receptionist's slug.

        Returns:
            The object key.
        """
        return thumbnail_object_key(slug)

    def _delete_files(self, slug: str) -> None:
        """
        Delete the receptionist video's files.

        Args:
            slug: The receptionist's slug.
        """
        delete_files_for_slug(slug)


assistant_video_service = AssistantVideoService()
