"""
What the receptionist sells through the core's campaigns: its demo page, its video, its price.

The variables, guards and values are the ones the core's campaign engine applied before the receptionist left the
core: a template linking the receptionist needs the prospect's active assistant, a template whose only door is the
receptionist's video needs that video (and the campaign's video switch on), and a sent message carrying the
assistant's link starts its demo countdown.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import ClassVar

from sqlalchemy.orm import Session

from core.product_modules.campaign_offer import CampaignOffer, OfferLifetime, PreviewThumbnail
from devleadhunter_receptionist.models.ai_assistant import AiAssistant
from devleadhunter_receptionist.services.assistant_pricing_service import AssistantPricingService
from devleadhunter_receptionist.services.assistant_service import ai_assistant_service
from devleadhunter_receptionist.services.receptionist_wording import ReceptionistWording
from devleadhunter_receptionist.sms_templates import RECEPTIONIST_SMS_TEMPLATES
from enums.demo_video_status import DemoVideoStatus
from enums.sms_message_kind import SmsMessageKind
from models.prospect_db import ProspectDB
from models.sms_message import SmsMessage
from services.country_profiles import CountryProfile, CountryProfiles
from services.email_variables import EmailVariables
from services.sms.templates import SmsTemplate
from services.sms_variables import SmsVariables
from services.tracking_links import email_tracked_link, sms_tracked_link

ASSISTANT_LINK: str = "lien_assistant"
RECEPTIONIST_FIRST_NAME: str = "prenom_receptionniste"
RECEPTIONIST: str = "receptionniste"
VIRTUAL_ASSISTANT: str = "assistant_virtuel"
ASSISTANT_VIDEO_LINK: str = "lien_video_assistant"
ASSISTANT_VIDEO_THUMBNAIL: str = "vignette_video_assistant"
PRICE_ASSISTANT: str = "prix_assistant"

_WORDING_VARIABLES: tuple[str, ...] = (PRICE_ASSISTANT, RECEPTIONIST_FIRST_NAME, RECEPTIONIST, VIRTUAL_ASSISTANT)
# The receptionist's pages in an SMS body: its demo (/ia/…) or its video (/va/…), the short links (/s/ia/…) included.
_ASSISTANT_PAGE_LINK: re.Pattern[str] = re.compile(r"/(?:s/)?(?:ia|va)/[\w-]+")
_VIDEO_THUMBNAIL_ALT: str = "Votre réceptionniste en vidéo"


class ReceptionistCampaignOffer(CampaignOffer):
    """The receptionist's demo, as the campaign engine links, guards and renders it."""

    module_key: ClassVar[str] = "ai-assistant"
    offer_label: ClassVar[str] = "AI assistant"
    expired_offer_skip_reason: ClassVar[str] = "Assistant expiré avant la relance"

    email_link_variables: ClassVar[tuple[str, ...]] = (ASSISTANT_LINK, ASSISTANT_VIDEO_LINK, ASSISTANT_VIDEO_THUMBNAIL)
    email_video_variables: ClassVar[tuple[str, ...]] = (ASSISTANT_VIDEO_LINK, ASSISTANT_VIDEO_THUMBNAIL)
    email_primary_link_variable: ClassVar[str | None] = ASSISTANT_LINK
    email_offer_variables: ClassVar[tuple[str, ...]] = (*email_link_variables, *_WORDING_VARIABLES)
    sms_link_variables: ClassVar[tuple[str, ...]] = (ASSISTANT_LINK, ASSISTANT_VIDEO_LINK)
    sms_video_variables: ClassVar[tuple[str, ...]] = (ASSISTANT_VIDEO_LINK,)
    sms_offer_variables: ClassVar[tuple[str, ...]] = (*sms_link_variables, *_WORDING_VARIABLES)
    preview_link_variables: ClassVar[tuple[str, ...]] = (ASSISTANT_LINK,)
    preview_thumbnails: ClassVar[tuple[PreviewThumbnail, ...]] = (
        PreviewThumbnail(
            thumbnail_variable=ASSISTANT_VIDEO_THUMBNAIL,
            link_variable=ASSISTANT_VIDEO_LINK,
            alt_text=_VIDEO_THUMBNAIL_ALT,
        ),
    )
    email_price_variables: ClassVar[tuple[str, ...]] = (PRICE_ASSISTANT,)

    missing_offer_skip_reason: ClassVar[str] = "Pas d'assistant IA actif"
    missing_video_skip_reason: ClassVar[str] = "Pas de vidéo de réceptionniste prête"
    missing_offer_launch_summary: ClassVar[str] = "faute d'assistant IA actif"

    @staticmethod
    def active_assistant(db: Session, *, prospect_id: int, user_id: int) -> AiAssistant | None:
        """
        The sender's active assistant for the prospect, the demo every receptionist variable points to.

        Args:
            db: Active database session.
            prospect_id: The prospect.
            user_id: The sending user.

        Returns:
            The assistant, or None.
        """
        return ai_assistant_service.get_active_for_prospect(db, prospect_id=prospect_id, user_id=user_id)

    @staticmethod
    def video_urls(assistant: AiAssistant | None) -> tuple[str, str]:
        """
        An assistant's prospection video: (player page URL, thumbnail URL).

        Empty strings without an active assistant or while its video is not ready — a template pairing
        ``{vignette_video_assistant}`` with ``{lien_assistant}`` then degrades to that live link, while a template with
        the video as its only door is held back by the queue guard until the video exists.

        Args:
            assistant: The sender's active assistant for the prospect, or None.

        Returns:
            The (video page URL, thumbnail URL) pair, or ("", "").
        """
        from devleadhunter_receptionist.services.assistant_video_service import public_thumbnail_url, video_page_url

        if assistant is None or assistant.video_status != DemoVideoStatus.READY.value:
            return "", ""
        return video_page_url(assistant.slug), public_thumbnail_url(assistant.slug, assistant.video_generated_at)

    def has_active_offer(self, db: Session, *, prospect_id: int, user_id: int) -> bool:
        """Whether the prospect has an active assistant of this user (source of ``{lien_assistant}``)."""
        return self.active_assistant(db, prospect_id=prospect_id, user_id=user_id) is not None

    def has_ready_video(self, db: Session, *, prospect_id: int, user_id: int) -> bool:
        """Whether the prospect's active receptionist of this user has a generated video."""
        return bool(self.video_urls(self.active_assistant(db, prospect_id=prospect_id, user_id=user_id))[0])

    def offer_lifetime(self, db: Session, *, prospect_id: int, user_id: int) -> OfferLifetime:
        """How long the prospect's receptionist demo lives; one whose countdown has not started lives for any follow-up."""
        assistant: AiAssistant | None = self.active_assistant(db, prospect_id=prospect_id, user_id=user_id)
        return OfferLifetime(
            has_offer=assistant is not None, expires_at=assistant.expires_at if assistant is not None else None
        )

    def email_variables(
        self, db: Session, prospect: ProspectDB, *, user_id: int, include_video: bool, variant: str | None
    ) -> dict[str, str]:
        """
        The receptionist's email variables for one prospect, its active assistant looked up once for all of them.

        Its links are real anchors stamped with the email channel and the A/B variant like the site's; its video
        stays out while the campaign's video switch is off; its price is written as the prospect reads it in his
        country, without « ≈ ».
        """
        assistant: AiAssistant | None = self.active_assistant(db, prospect_id=prospect.id, user_id=user_id)
        video_link, video_thumbnail = self.video_urls(assistant) if include_video else ("", "")
        if video_link:
            video_link = email_tracked_link(video_link, variant)
        assistant_link: str = (
            EmailVariables.build_demo_link_html(
                email_tracked_link(ai_assistant_service.page_url(assistant.slug), variant)
            )
            if assistant is not None
            else ""
        )
        country: CountryProfile = CountryProfiles.get(prospect.country)
        return {
            ASSISTANT_LINK: assistant_link,
            RECEPTIONIST_FIRST_NAME: assistant.assistant_name if assistant is not None else "",
            RECEPTIONIST: ReceptionistWording.receptionist(assistant),
            VIRTUAL_ASSISTANT: ReceptionistWording.virtual_assistant(assistant),
            ASSISTANT_VIDEO_LINK: video_link,
            ASSISTANT_VIDEO_THUMBNAIL: EmailVariables.build_video_thumbnail_html(
                video_link, video_thumbnail, _VIDEO_THUMBNAIL_ALT
            ),
            PRICE_ASSISTANT: country.format_price_without_approximation(
                AssistantPricingService.monthly_price_cents(db, user_id)
            ),
        }

    def expiry_date_without_demo_link(self, db: Session, prospect: ProspectDB, *, user_id: int) -> str | None:
        """``{date_expiration}`` of a receptionist email: the day the prospect's assistant demo goes offline."""
        assistant: AiAssistant | None = self.active_assistant(db, prospect_id=prospect.id, user_id=user_id)
        if assistant is None:
            return None
        return EmailVariables.expiry_label(assistant.demo_link_sent_at, assistant.expires_at)

    def email_button_labels(self, variables: dict[str, str]) -> dict[str, str]:
        """« Parler à Sofia » under the assistant link (« Voir la démo » without a name); no button under its video."""
        first_name: str = variables.get(RECEPTIONIST_FIRST_NAME, "")
        return {
            ASSISTANT_LINK: f"Parler à {first_name}" if first_name else "Voir la démo",
            ASSISTANT_VIDEO_THUMBNAIL: "",
        }

    def sms_variables(self, db: Session, prospect: ProspectDB, *, user_id: int) -> dict[str, str]:
        """The receptionist's SMS variables for one prospect: its links in the SMS short form, tracked like the site's."""
        assistant: AiAssistant | None = self.active_assistant(db, prospect_id=prospect.id, user_id=user_id)
        assistant_url: str = ai_assistant_service.page_url(assistant.slug) if assistant is not None else ""
        assistant_video_url: str = self.video_urls(assistant)[0]
        country: CountryProfile = CountryProfiles.get(prospect.country)
        return {
            ASSISTANT_LINK: SmsVariables.as_sms_link(sms_tracked_link(assistant_url)) if assistant_url else "",
            RECEPTIONIST_FIRST_NAME: assistant.assistant_name if assistant is not None else "",
            RECEPTIONIST: ReceptionistWording.receptionist(assistant),
            VIRTUAL_ASSISTANT: ReceptionistWording.virtual_assistant(assistant),
            ASSISTANT_VIDEO_LINK: (
                SmsVariables.as_sms_link(sms_tracked_link(assistant_video_url)) if assistant_video_url else ""
            ),
            # Resolved from user_id (the assistant monthly price is per-user, like {prix}).
            PRICE_ASSISTANT: country.format_price_without_approximation(
                AssistantPricingService.monthly_price_cents(db, user_id)
            ),
        }

    def record_message_sent(self, db: Session, *, prospect_id: int, user_id: int, sent_at: datetime, body: str) -> None:
        """Start the demo countdown of the prospect's assistant when the sent email or SMS carries its link."""
        ai_assistant_service.maybe_start_ttl_after_demo_email(
            db, user_id=user_id, prospect_id=prospect_id, sent_at=sent_at, body_html=body
        )

    def sms_templates(self) -> list[SmsTemplate]:
        """The receptionist's SMS templates (first contacts and relances)."""
        return list(RECEPTIONIST_SMS_TEMPLATES)

    def owns_sms_message(self, message: SmsMessage) -> bool:
        """A receptionist SMS: a service message (its alerts, confirmations, reminders), or one linking its pages."""
        return message.kind == SmsMessageKind.SERVICE.value or bool(_ASSISTANT_PAGE_LINK.search(message.body or ""))


receptionist_campaign_offer = ReceptionistCampaignOffer()
