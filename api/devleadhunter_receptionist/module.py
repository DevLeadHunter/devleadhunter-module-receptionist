"""The receptionist as a DevLeadHunter product module: what it plugs into the core."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.product_modules.contract import BackgroundLoop, DeliverableExpiry, ProductModule, StorageKind

if TYPE_CHECKING:
    from fastapi import APIRouter, FastAPI

    from core.product_modules.campaign_offer import CampaignOffer
    from core.product_modules.sidecar import SidecarVideoBuildApi
    from schemas.notification import DemoEventIn

# The receptionist's tracked migrations, in the order the core ran them before the module left it (their names are
# already recorded in production's ``schema_migrations``: they never run twice).
_MIGRATIONS: tuple[str, ...] = (
    "add_ai_assistants_table",
    "add_ai_assistant_leads_table",
    "add_ai_assistant_video",
    "seed_assistant_email_templates",
    "seed_assistant_franc_email_template",
    "add_user_assistant_pricing",
    "fix_assistant_franc_price_variable",
    "add_ai_assistant_subscriptions_table",
    "rewrite_assistant_franc_emails",
    "add_ai_assistant_conversation_tables",
    "add_ai_assistant_requests_table",
    "add_ai_assistant_alerts",
    "add_ai_assistant_photos_table",
    "add_ai_assistant_eu_only",
    "raise_assistant_default_price",
    "rewrite_assistant_emails_missed_requests",
    "add_ai_assistant_conversations_is_test",
    "add_assistant_subscription_activated_at",
    "add_ai_assistant_reports_table",
    "add_assistant_subscription_cancel_at_period_end",
    "add_ai_assistant_request_appointment_slots",
    "add_ai_assistant_calendars_tables",
    "add_ai_assistant_documents_table",
    "convert_ai_assistant_tables_to_utf8mb4",
    "add_ai_assistant_messages_photo_url",
    "seed_assistant_video_email_template",
    "add_assistant_video_thumbnail_to_first_emails",
    "add_ai_assistant_start_columns",
    "add_ai_assistant_request_outcome",
    "add_ai_assistant_limits",
    "add_ai_assistant_request_event",
    "add_ai_assistant_client_link_version",
    "add_ai_assistant_message_cap_alerted_on",
    "rename_assistant_language_lu_to_lb",
    "add_assistant_subscription_payment_failed_invoice_id",
    "add_ai_assistant_mailbox_enabled",
    "add_ai_assistant_mailbox_tables",
    "add_ai_assistant_custom_avatar",
    "add_ai_assistant_video_desktop_requested_at",
    "add_ai_assistant_owner_settings_table",
)


class ReceptionistModule(ProductModule):
    """The AI receptionist: a chat on the business's site or page, its requests, its agenda, its subscription."""

    key: ClassVar[str] = "ai-assistant"
    label: ClassVar[str] = "Réceptionniste IA"
    description: ClassVar[str] = (
        "Une réceptionniste IA par prospect : sa page démo, le widget à poser sur un site, les demandes reçues, "
        "l'espace client et l'abonnement mensuel."
    )
    enabled_by_default: ClassVar[bool] = True
    notification_tag: ClassVar[str] = "🤖 Assistant IA"
    demo_beacon_prefix: ClassVar[str | None] = "assistant_video_"

    def load(self) -> None:
        """Import every model of the module (their tables join the core metadata) and set its loggers' levels."""
        from devleadhunter_receptionist import models

        for model_module in pkgutil.iter_modules(models.__path__):
            importlib.import_module(f"{models.__name__}.{model_module.name}")
        # The per-call provider / latency / cost line of the models (INFO, above the root level).
        logging.getLogger("devleadhunter_receptionist.services.llm_router").setLevel(logging.INFO)
        # The size of each assistant prompt (INFO): how much of the site and the documents it carries.
        logging.getLogger("devleadhunter_receptionist.services.chat_service").setLevel(logging.INFO)

    def routers(self) -> list[APIRouter]:
        """The module's routers, the owner's own routes before ``/public/{slug}``, before ``/{assistant_id}/…``."""
        from devleadhunter_receptionist.routes import (
            ai_assistant_client_space,
            ai_assistant_faq,
            ai_assistant_pricing,
            ai_assistant_requests,
            ai_assistant_sources,
            ai_assistant_subscriptions,
            ai_assistant_widget,
            ai_assistants,
        )

        return [
            # « /ai-assistants/pricing » before « /ai-assistants/{assistant_id} », which would take it for an id.
            ai_assistant_pricing.router,
            ai_assistants.router,
            ai_assistant_requests.router,
            ai_assistant_subscriptions.router,
            ai_assistant_widget.router,
            ai_assistant_client_space.router,
            ai_assistant_sources.router,
            ai_assistant_faq.router,
        ]

    def background_loops(self) -> list[BackgroundLoop]:
        """Demo expiry and purges, request analysis, monthly reports, site re-reads, mailbox sync."""
        from devleadhunter_receptionist.services.cleanup_service import run_ai_assistant_cleanup_loop
        from devleadhunter_receptionist.services.mailbox_sync import ai_assistant_mailbox_sync
        from devleadhunter_receptionist.services.report_service import ai_assistant_report_service
        from devleadhunter_receptionist.services.request_runner import AiAssistantRequestRunner
        from devleadhunter_receptionist.services.source_service import ai_assistant_source_service

        return [
            run_ai_assistant_cleanup_loop,
            AiAssistantRequestRunner.run_loop,
            ai_assistant_report_service.run_loop,
            ai_assistant_source_service.run_loop,
            ai_assistant_mailbox_sync.run_loop,
        ]

    def migrations(self) -> list[tuple[str, str]]:
        """The module's tracked migrations, under their historical names."""
        return [(name, f"devleadhunter_receptionist.migrations.{name}") for name in _MIGRATIONS]

    def campaign_offer(self) -> CampaignOffer | None:
        """The receptionist's demo, video and price in the campaigns."""
        from devleadhunter_receptionist.offer import receptionist_campaign_offer

        return receptionist_campaign_offer

    def email_template_library(self) -> list[dict[str, object]]:
        """The receptionist's cold emails (« Réceptionniste IA - … »)."""
        from devleadhunter_receptionist.email_templates import RECEPTIONIST_EMAIL_TEMPLATES

        return list(RECEPTIONIST_EMAIL_TEMPLATES)

    async def handle_stripe_event(self, db: Session, event: dict[str, Any]) -> str | None:
        """The receptionist's subscriptions: activation, lifecycle sync, failed payments."""
        from devleadhunter_receptionist.services.stripe_events import receptionist_stripe_events

        return await receptionist_stripe_events.handle(db, event)

    async def handle_demo_beacon(self, db: Session, payload: DemoEventIn) -> None:
        """Notify the owner of an event on a receptionist's prospection video page; unknown slugs are ignored."""
        from devleadhunter_receptionist.services.assistant_service import ai_assistant_service
        from devleadhunter_receptionist.services.receptionist_notifications import receptionist_notifications
        from services.robot_visit_detector import VisitorBrowser

        assistant = ai_assistant_service.get_by_slug(db, payload.demo_slug)
        if assistant is None:
            return
        await receptionist_notifications.notify_assistant_video_event(
            db,
            user_id=assistant.user_id,
            prospect_id=assistant.prospect_id,
            event_name=payload.event,
            fallback_name=assistant.slug,
            channel=payload.channel,
            browser=VisitorBrowser(
                timezone_name=payload.browser_timezone,
                language=payload.browser_language,
                is_automated=payload.is_automated_browser,
            ),
        )

    def demo_slugs(self, db: Session, *, user_id: int) -> list[tuple[str, int | None]]:
        """The user's live receptionists, as (slug, prospect id)."""
        from devleadhunter_receptionist.models.ai_assistant import AiAssistant

        rows = (
            db.query(AiAssistant.slug, AiAssistant.prospect_id)
            .filter(AiAssistant.user_id == user_id, AiAssistant.deleted_at.is_(None))
            .all()
        )
        return [(slug, prospect_id) for slug, prospect_id in rows if slug]

    def is_demo_slug_taken(self, db: Session, slug: str, *, prospect_id: int | None) -> bool:
        """Whether a receptionist of another prospect, or of no prospect, holds the slug."""
        from sqlalchemy import or_

        from devleadhunter_receptionist.models.ai_assistant import AiAssistant

        holders = db.query(AiAssistant.id).filter(AiAssistant.slug == slug)
        if prospect_id is not None:
            holders = holders.filter(or_(AiAssistant.prospect_id.is_(None), AiAssistant.prospect_id != prospect_id))
        return holders.first() is not None

    def tracking_event_labels(self) -> dict[str, str]:
        """The timeline labels of the receptionist's video page."""
        from devleadhunter_receptionist.tracking import VIDEO_PAGE_EVENT_LABELS

        return dict(VIDEO_PAGE_EVENT_LABELS)

    def lead_score_event_aliases(self) -> dict[str, str]:
        """The receptionist's video events score as the site video's."""
        from devleadhunter_receptionist.tracking import VIDEO_PAGE_LEAD_SCORE_ALIASES

        return dict(VIDEO_PAGE_LEAD_SCORE_ALIASES)

    def posthog_event_names(self) -> tuple[str, ...]:
        """The receptionist's video events, read with the sites' in PostHog."""
        from devleadhunter_receptionist.tracking import VIDEO_PAGE_POSTHOG_EVENTS

        return VIDEO_PAGE_POSTHOG_EVENTS

    def storage_kinds(self) -> list[StorageKind]:
        """The receptionist's video and thumbnail (they die with its demo), its quote photos, documents, portraits."""
        from devleadhunter_receptionist.services.photo_service import RETENTION as PHOTO_RETENTION
        from devleadhunter_receptionist.services.receptionist_storage import ReceptionistStorage

        return [
            StorageKind(
                kind="assistant_video",
                prefix=f"{ReceptionistStorage.VIDEOS_ASSISTANT_PREFIX}/",
                label="Vidéo (réceptionniste)",
                filter_label="Vidéos réceptionniste",
                media="video",
                is_demo_deliverable=True,
                is_prospection_video=True,
            ),
            StorageKind(
                kind="assistant_thumbnail",
                # The trailing slash keeps the quote photos (``images/assistant-photos/``) out.
                prefix=f"{ReceptionistStorage.IMAGES_ASSISTANT_PREFIX}/",
                label="Vignette (réceptionniste)",
                filter_label="Vignettes réceptionniste",
                media="image",
                is_demo_deliverable=True,
            ),
            StorageKind(
                kind="assistant_photo",
                prefix=f"{ReceptionistStorage.IMAGES_ASSISTANT_PHOTOS_PREFIX}/",
                label="Photo de devis (assistant)",
                filter_label="Photos de devis",
                media="image",
                retention_days=PHOTO_RETENTION.days,
            ),
            StorageKind(
                kind="assistant_document",
                prefix=f"{ReceptionistStorage.DOCUMENTS_ASSISTANT_PREFIX}/",
                label="Document (assistant)",
                filter_label="Documents assistants",
                media="file",
            ),
            StorageKind(
                kind="assistant_avatar",
                prefix=f"{ReceptionistStorage.IMAGES_ASSISTANT_AVATARS_PREFIX}/",
                label="Portrait (réceptionniste)",
                filter_label="Portraits réceptionniste",
                media="image",
            ),
        ]

    def deliverable_expiries(self, db: Session, slugs: set[str], now: datetime) -> dict[str, DeliverableExpiry]:
        """
        When the receptionists' videos and thumbnails expire, anchored on their demo like a site's.

        A sold receptionist is permanent; one whose link was never sent has not started its countdown; a deleted one
        is left out, so its files read as leftovers the purge removes.
        """
        from devleadhunter_receptionist.enums.ai_assistant_status import AiAssistantStatus
        from devleadhunter_receptionist.models.ai_assistant import AiAssistant
        from models.prospect_db import ProspectDB

        if not slugs:
            return {}
        rows = (
            db.query(
                AiAssistant.slug,
                AiAssistant.status,
                AiAssistant.demo_link_sent_at,
                AiAssistant.expires_at,
                func.coalesce(ProspectDB.name, AiAssistant.business_name).label("name"),
            )
            .outerjoin(ProspectDB, ProspectDB.id == AiAssistant.prospect_id)
            .filter(AiAssistant.slug.in_(slugs), AiAssistant.deleted_at.is_(None))
            .all()
        )
        expiries: dict[str, DeliverableExpiry] = {}
        for row in rows:
            if row.status == AiAssistantStatus.DELIVERED.value:
                expiries[row.slug] = DeliverableExpiry(
                    is_expired=False, expires_in_days=None, ttl_pending=False, name=row.name
                )
                continue
            if row.demo_link_sent_at is None or row.expires_at is None:
                expiries[row.slug] = DeliverableExpiry(
                    is_expired=False, expires_in_days=None, ttl_pending=True, name=row.name
                )
                continue
            expires_at: datetime = (
                row.expires_at.replace(tzinfo=UTC) if row.expires_at.tzinfo is None else row.expires_at
            )
            if expires_at <= now:
                expiries[row.slug] = DeliverableExpiry(
                    is_expired=True, expires_in_days=None, ttl_pending=False, name=row.name
                )
            else:
                expiries[row.slug] = DeliverableExpiry(
                    is_expired=False,
                    expires_in_days=max(0, (expires_at - now).days),
                    ttl_pending=False,
                    name=row.name,
                )
        return expiries

    def ready_video_slugs(self, db: Session) -> set[str]:
        """The live receptionists whose prospection video is ready."""
        from devleadhunter_receptionist.models.ai_assistant import AiAssistant
        from enums.demo_video_status import DemoVideoStatus

        return {
            slug
            for (slug,) in db.query(AiAssistant.slug)
            .filter(AiAssistant.video_status == DemoVideoStatus.READY.value, AiAssistant.deleted_at.is_(None))
            .all()
            if slug
        }

    def register_sidecar_routes(self, app: FastAPI, video_builds: SidecarVideoBuildApi) -> None:
        """The desktop build of the receptionist's prospection video."""
        from devleadhunter_receptionist.sidecar import register_receptionist_sidecar_routes

        register_receptionist_sidecar_routes(app, video_builds)
