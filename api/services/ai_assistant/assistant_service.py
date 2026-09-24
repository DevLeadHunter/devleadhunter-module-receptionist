"""Generate and serve a prospect's AI assistant.

Mirrors the demo-site engine: one assistant generated per prospect, from the same enrichment, served
publicly by slug and answering visitors. No Storyblok — the assistant renders from ``knowledge_json``.
"""

import logging
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from core.config import settings
from enums.ai_assistant_request import AiAssistantRequestType
from enums.ai_assistant_status import AiAssistantStatus
from enums.demo_site_status import DemoSiteStatus
from enums.website_status import WebsiteStatus
from models.ai_assistant import AiAssistant
from models.demo_site import DemoSite
from models.prospect_db import ProspectDB
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.knowledge_builder import ai_assistant_knowledge_builder
from services.ai_assistant.website_crawler import ai_assistant_website_crawler
from services.ai_assistant.website_sync import AiAssistantWebsiteSync
from services.enrichment_service import enrichment_service
from services.mistral_service import mistral_service
from services.sms.phone_normalizer import to_e164_mobile

logger = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


_PUBLICLY_SERVED_STATUSES: tuple[str, ...] = (AiAssistantStatus.ACTIVE.value, AiAssistantStatus.DELIVERED.value)


class AiAssistantService:
    """Creates an assistant for a prospect and serves it publicly by slug."""

    def build_fields(
        self,
        *,
        business_name: str,
        city: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        country: str | None = None,
        logo_url: str | None = None,
        enrichment: dict[str, Any] | None = None,
        assistant_name: str | None = None,
        languages: list[str] | None = None,
        tone: str | None = None,
        use_brand_color: bool = True,
        website: dict[str, Any] | None = None,
        generated_site: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble the persistable fields of an assistant from a prospect's data (pure, no DB).

        Args:
            website: The crawl of the prospect's own site, when it has one.
            generated_site: The ``content_json`` of the demo site generated for the prospect, when one exists.

        Returns:
            A dict of column values for :class:`AiAssistant` (identity, persona, ``knowledge_json``).
        """
        config = ai_assistant_config_builder.build_config(
            country=country,
            logo_url=logo_url,
            assistant_name=assistant_name,
            languages=languages,
            tone=tone,
            use_brand_color=use_brand_color,
        )
        knowledge = ai_assistant_knowledge_builder.build_knowledge(
            business_name=business_name,
            city=city,
            address=address,
            phone=phone,
            email=email,
            enrichment=enrichment,
            website=website,
            generated_site=generated_site,
        )
        # The widget accent lives with the knowledge so the public endpoint serves it in one read.
        knowledge["palette"] = {"accent": config["accent_color"]}
        return {
            "business_name": business_name,
            "city": city,
            "phone": phone,
            "email": email,
            "description": knowledge["identity"].get("description"),
            "assistant_name": config["assistant_name"],
            "languages": config["languages"],
            "tone": config["tone"],
            "knowledge_json": knowledge,
            "use_brand_color": use_brand_color,
        }

    def update(self, db: Session, assistant: AiAssistant, fields: dict[str, Any]) -> AiAssistant:
        """Apply owner edits (branding/persona/alerts/EU only) to an assistant, then persist.

        Only keys present in ``fields`` are touched, so a partial edit never wipes the rest.
        The accent lives in ``knowledge_json['palette']``, reassigned as a new dict so SQLAlchemy
        detects the JSON change. An empty string clears a value (neutral accent, default persona,
        no alert number).

        Args:
            db: Active database session.
            assistant: The row to edit.
            fields: The provided fields (from ``model_dump(exclude_unset=True)``).

        Returns:
            The refreshed assistant row.

        Raises:
            ValueError: When the alert number cannot receive an SMS, or « EU only » is asked without a
                Mistral key (nothing is saved).
        """
        if fields.get("eu_only") and not mistral_service.is_configured:
            raise ValueError("« EU only » impossible : la clé Mistral (MISTRAL_API_KEY) n'est pas configurée")
        if "alert_phone" in fields:
            raw_phone = (fields["alert_phone"] or "").strip()
            phone = to_e164_mobile(raw_phone, country=self.business_country(db, assistant)) if raw_phone else None
            if raw_phone and phone is None:
                raise ValueError(
                    "Numéro d'alerte invalide : un mobile est requis, 06 / 07 en France, "
                    "au format international ailleurs (+352…, +32…)"
                )
            assistant.alert_phone_e164 = phone
        for flag in ("alert_sms_enabled", "alert_email_enabled"):
            if flag in fields and fields[flag] is not None:
                setattr(assistant, flag, bool(fields[flag]))
        if "alert_sms_types" in fields and fields["alert_sms_types"] is not None:
            chosen = {AiAssistantRequestType(value) for value in fields["alert_sms_types"]}
            assistant.alert_sms_types = [item.value for item in AiAssistantRequestType if item in chosen]
        for hour in ("alert_quiet_start_hour", "alert_quiet_end_hour"):
            if hour in fields and fields[hour] is not None:
                setattr(assistant, hour, int(fields[hour]))
        if "eu_only" in fields and fields["eu_only"] is not None:
            assistant.eu_only = bool(fields["eu_only"])
        if "assistant_name" in fields:
            assistant.assistant_name = (fields["assistant_name"] or "").strip() or assistant.assistant_name
        if "business_name" in fields:
            assistant.business_name = (fields["business_name"] or "").strip() or assistant.business_name
        if "languages" in fields:
            assistant.languages = fields["languages"] or []
        if "tone" in fields:
            assistant.tone = (fields["tone"] or "").strip() or None
        if "use_brand_color" in fields:
            assistant.use_brand_color = bool(fields["use_brand_color"])
        if "accent_color" in fields:
            knowledge = dict(assistant.knowledge_json or {})
            palette = dict(knowledge.get("palette") or {})
            palette["accent"] = (fields["accent_color"] or "").strip() or None
            knowledge["palette"] = palette
            assistant.knowledge_json = knowledge
        db.commit()
        db.refresh(assistant)
        return assistant

    @staticmethod
    def business_category(db: Session, assistant: AiAssistant) -> str | None:
        """The business's Google Maps category (its prospect's), when known."""
        if assistant.prospect_id is None:
            return None
        return db.query(ProspectDB.category).filter(ProspectDB.id == assistant.prospect_id).scalar()

    @staticmethod
    def business_country(db: Session, assistant: AiAssistant) -> str:
        """ISO code of the business's country (its prospect's), France when unknown."""
        if assistant.prospect_id is None:
            return "FR"
        country = db.query(ProspectDB.country).filter(ProspectDB.id == assistant.prospect_id).scalar()
        return country or "FR"

    def create(
        self,
        db: Session,
        *,
        user_id: int,
        business_name: str,
        prospect_id: int | None = None,
        city: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        country: str | None = None,
        logo_url: str | None = None,
        enrichment: dict[str, Any] | None = None,
        assistant_name: str | None = None,
        languages: list[str] | None = None,
        tone: str | None = None,
        use_brand_color: bool = True,
        website: dict[str, Any] | None = None,
        generated_site: dict[str, Any] | None = None,
    ) -> AiAssistant:
        """Create and persist an active assistant, returning the stored row."""
        fields = self.build_fields(
            business_name=business_name,
            city=city,
            address=address,
            phone=phone,
            email=email,
            country=country,
            logo_url=logo_url,
            enrichment=enrichment,
            assistant_name=assistant_name,
            languages=languages,
            tone=tone,
            use_brand_color=use_brand_color,
            website=website,
            generated_site=generated_site,
        )
        assistant = AiAssistant(
            user_id=user_id,
            prospect_id=prospect_id,
            slug=self._unique_slug(db, business_name),
            status=AiAssistantStatus.ACTIVE.value,
            **fields,
        )
        db.add(assistant)
        db.commit()
        db.refresh(assistant)

        # Prospection video: auto-generate in the background as soon as the assistant is active, if the
        # user configured their « assistant » webcam clip with the option on (covers single + bulk).
        if assistant.status == AiAssistantStatus.ACTIVE.value:
            from services.assistant_video_service import assistant_video_service

            assistant_video_service.maybe_start_auto_generation(db, assistant, user_id)

        # A campaign may have left this prospect out for lacking an assistant: it can join the queue now.
        self._enqueue_ready_prospect(db, prospect_id, user_id)
        return assistant

    async def create_for_prospect(self, db: Session, *, user_id: int, prospect: ProspectDB) -> AiAssistant:
        """Generate an assistant for a prospect: enrichment, their own website and the site generated for them."""
        enrichment = enrichment_service.to_dict(await enrichment_service.ensure_enriched(db, user_id, prospect))
        website = await self.crawl_prospect_website(prospect)
        generated_site = self._generated_site_content(db, user_id=user_id, prospect_id=prospect.id)
        return self.create(
            db,
            user_id=user_id,
            prospect_id=prospect.id,
            business_name=prospect.name,
            city=prospect.city,
            address=prospect.address,
            phone=prospect.phone,
            email=prospect.email,
            country=prospect.country,
            logo_url=(enrichment or {}).get("logo_url"),
            enrichment=enrichment,
            website=website,
            generated_site=generated_site,
        )

    def regenerate(
        self,
        db: Session,
        *,
        assistant: AiAssistant,
        prospect: ProspectDB,
        enrichment: dict[str, Any] | None,
        website: dict[str, Any] | None = None,
        generated_site: dict[str, Any] | None = None,
    ) -> AiAssistant:
        """Rebuild an assistant's knowledge from the prospect's latest data, keeping look and voice.

        Regenerate answers « the prospect's data (or the knowledge engine) improved since I
        generated this assistant ». It refreshes the grounding facts and contact details but never
        the branding or persona: the displayed name, assistant name, tone, languages, accent colour
        and slug are all preserved, so a link already sent keeps working and looking the same.

        Args:
            db: Active database session.
            assistant: The assistant to rebuild.
            prospect: The prospect it was generated from (source of the refreshed facts).
            enrichment: The prospect's enrichment as a dict, or ``None``.
            website: A fresh crawl of the prospect's own site, or ``None``.
            generated_site: The ``content_json`` of the demo site generated for the prospect, or ``None``.

        Returns:
            The refreshed assistant row.
        """
        existing_accent = (dict((assistant.knowledge_json or {}).get("palette") or {})).get("accent")
        fields = self.build_fields(
            business_name=assistant.business_name,
            city=prospect.city,
            address=prospect.address,
            phone=prospect.phone,
            email=prospect.email,
            country=prospect.country,
            logo_url=(enrichment or {}).get("logo_url"),
            enrichment=enrichment,
            use_brand_color=assistant.use_brand_color,
            website=website,
            generated_site=generated_site,
        )
        knowledge = fields["knowledge_json"]
        knowledge["palette"] = {"accent": existing_accent}
        # What was set up on the assistant survives: its documents and its source switches.
        previous = assistant.knowledge_json or {}
        for key in ("documents", "sources"):
            if key in previous:
                knowledge[key] = previous[key]
        previous_site = previous.get("website") if isinstance(previous.get("website"), dict) else None
        read_at = datetime.now(UTC).replace(tzinfo=None)
        if website is not None:
            knowledge["website_sync"] = AiAssistantWebsiteSync.record(previous_site, website, at=read_at)
        elif previous_site and self.has_readable_website(prospect):
            # The site cannot be read right now: its previous pages stay, like in the weekly re-read.
            knowledge["website"] = previous_site
            knowledge["website_sync"] = AiAssistantWebsiteSync.record(previous_site, None, at=read_at)
        assistant.city = fields["city"]
        assistant.phone = fields["phone"]
        assistant.email = fields["email"]
        assistant.description = fields["description"]
        assistant.knowledge_json = knowledge
        db.commit()
        db.refresh(assistant)
        return assistant

    async def regenerate_for_prospect(
        self, db: Session, *, assistant: AiAssistant, prospect: ProspectDB
    ) -> AiAssistant:
        """Re-enrich the prospect and re-crawl their site, then rebuild the knowledge (keeps branding)."""
        enrichment = enrichment_service.to_dict(
            await enrichment_service.ensure_enriched(db, assistant.user_id, prospect)
        )
        website = await self.crawl_prospect_website(prospect)
        generated_site = self._generated_site_content(db, user_id=assistant.user_id, prospect_id=prospect.id)
        # The enrichment and the read take seconds: take the assistant as it is now (a document added meanwhile).
        db.commit()
        db.refresh(assistant)
        return self.regenerate(
            db,
            assistant=assistant,
            prospect=prospect,
            enrichment=enrichment,
            website=website,
            generated_site=generated_site,
        )

    @staticmethod
    def has_readable_website(prospect: Any) -> bool:
        """Whether the prospect has a website worth reading (known, neither dead nor a placeholder)."""
        website = str(getattr(prospect, "website", None) or "").strip()
        status = getattr(prospect, "website_status", None)
        return bool(website) and status not in (WebsiteStatus.DEAD.value, WebsiteStatus.PLACEHOLDER.value)

    @classmethod
    async def crawl_prospect_website(cls, prospect: ProspectDB) -> dict[str, Any] | None:
        """The prospect's live website as crawl data, or None when there is no site worth reading."""
        if not cls.has_readable_website(prospect):
            return None
        return await ai_assistant_website_crawler.crawl((prospect.website or "").strip())

    @staticmethod
    def _generated_site_content(db: Session, *, user_id: int, prospect_id: int | None) -> dict[str, Any] | None:
        """The ``content_json`` of the newest demo site generated for the prospect, or None."""
        if not prospect_id:
            return None
        site: DemoSite | None = (
            db.query(DemoSite)
            .filter(
                DemoSite.user_id == user_id,
                DemoSite.prospect_id == prospect_id,
                DemoSite.status != DemoSiteStatus.DELETED.value,
                DemoSite.content_json.isnot(None),
            )
            .order_by(DemoSite.created_at.desc())
            .first()
        )
        return site.content_json if site is not None else None

    def start_demo_ttl(self, db: Session, assistant: AiAssistant, sent_at: datetime) -> bool:
        """Start the demo countdown from the first email or SMS carrying the assistant link; a no-op after.

        The demo dies ``demo_site_ttl_days`` after that first send, like a demo site. A sold assistant
        never counts down.

        Returns:
            True when ``expires_at`` was set by this send.
        """
        if assistant.demo_link_sent_at is not None or assistant.status != AiAssistantStatus.ACTIVE.value:
            return False
        sent_utc: datetime = _as_utc(sent_at)
        assistant.demo_link_sent_at = sent_utc
        assistant.expires_at = sent_utc + timedelta(days=settings.demo_site_ttl_days)
        db.commit()
        logger.info("Assistant demo TTL started for slug=%s expires_at=%s", assistant.slug, assistant.expires_at)
        return True

    def maybe_start_ttl_after_demo_email(
        self, db: Session, *, user_id: int, prospect_id: int, sent_at: datetime, body_html: str
    ) -> None:
        """Start the demo countdown when an outreach email ships the sender's assistant link."""
        assistant: AiAssistant | None = self.get_active_for_prospect(db, prospect_id=prospect_id, user_id=user_id)
        if assistant is None or not self.body_contains_assistant_link(assistant, body_html):
            return
        self.start_demo_ttl(db, assistant, sent_at)

    @staticmethod
    def accent_color(assistant: AiAssistant) -> str | None:
        """
        The widget accent, stored with the knowledge (``knowledge_json['palette']['accent']``).

        Args:
            assistant: The assistant.

        Returns:
            The accent colour, or None when the widget keeps the neutral one.
        """
        palette = (assistant.knowledge_json or {}).get("palette")
        accent = palette.get("accent") if isinstance(palette, dict) else None
        return accent if isinstance(accent, str) else None

    @staticmethod
    def body_contains_assistant_link(assistant: AiAssistant, body: str) -> bool:
        """Whether a rendered email or SMS body carries this assistant's public demo URL."""
        return f"/ia/{assistant.slug}" in (body or "")

    def expire_due_assistants(self, db: Session) -> int:
        """Expire the demo assistants past their countdown; a sold assistant is never touched.

        Returns:
            The number of assistants expired.
        """
        due: list[AiAssistant] = (
            db.query(AiAssistant)
            .filter(
                AiAssistant.status == AiAssistantStatus.ACTIVE.value,
                AiAssistant.deleted_at.is_(None),
                AiAssistant.demo_link_sent_at.isnot(None),
                AiAssistant.expires_at <= datetime.now(UTC),
            )
            .all()
        )
        for assistant in due:
            assistant.status = AiAssistantStatus.EXPIRED.value
            logger.info("Assistant demo expired for slug=%s", assistant.slug)
        if due:
            db.commit()
        return len(due)

    @staticmethod
    def get_for_owner(db: Session, assistant_id: int, user_id: int) -> AiAssistant | None:
        """
        One of the owner's assistants, deleted ones excluded.

        Args:
            db: Active database session.
            assistant_id: The assistant.
            user_id: The owner.

        Returns:
            The assistant, or None when it is not the owner's or was deleted.
        """
        return (
            db.query(AiAssistant)
            .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user_id, AiAssistant.deleted_at.is_(None))
            .first()
        )

    def get_active_for_prospect(self, db: Session, *, prospect_id: int, user_id: int) -> AiAssistant | None:
        """Return the user's newest active (demo) assistant for a prospect, or None.

        Prospection links the demo only: a sold (``delivered``) assistant is never prospected again,
        and on a shared prospect another member's assistant never leaks into this user's sends.
        """
        return (
            db.query(AiAssistant)
            .filter(
                AiAssistant.prospect_id == prospect_id,
                AiAssistant.user_id == user_id,
                AiAssistant.status == AiAssistantStatus.ACTIVE.value,
                AiAssistant.deleted_at.is_(None),
            )
            .order_by(AiAssistant.created_at.desc())
            .first()
        )

    def get_by_slug(self, db: Session, slug: str) -> AiAssistant | None:
        """Return the non-deleted assistant for a slug, whatever its status, or None."""
        return db.query(AiAssistant).filter(AiAssistant.slug == slug, AiAssistant.deleted_at.is_(None)).first()

    def get_public_by_slug(self, db: Session, slug: str) -> AiAssistant | None:
        """Return the publicly served, non-deleted assistant for a slug, or None.

        Serves the demo (``active``) and the sold assistant (``delivered``): a paying client's widget
        must never stop answering. Expired, failed and deleted assistants stay private.
        """
        return (
            db.query(AiAssistant)
            .filter(
                AiAssistant.slug == slug,
                AiAssistant.deleted_at.is_(None),
                AiAssistant.status.in_(_PUBLICLY_SERVED_STATUSES),
            )
            .first()
        )

    @staticmethod
    def _enqueue_ready_prospect(db: Session, prospect_id: int | None, user_id: int) -> None:
        """Append the prospect to the active campaigns that skipped him for lacking an assistant; never raises."""
        if not prospect_id:
            return
        try:
            from services.campaign_queue_service import CampaignQueueService

            added: int = CampaignQueueService(db).enqueue_ready_prospect(prospect_id, user_id)
            if added:
                logger.info(
                    "[Assistant] Assistant ready for prospect %d — auto-enqueued into %d campaign send(s)",
                    prospect_id,
                    added,
                )
        except Exception:
            logger.warning(
                "[Assistant] Auto re-enqueue after assistant ready failed for prospect %s", prospect_id, exc_info=True
            )

    def _unique_slug(self, db: Session, business_name: str) -> str:
        base_slug = self._slugify(business_name)[:80]
        candidate = base_slug
        suffix = 1
        while db.query(AiAssistant).filter(AiAssistant.slug == candidate).first() is not None:
            suffix += 1
            candidate = f"{base_slug}-{suffix}"
        return candidate

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
        return slug or "assistant"


ai_assistant_service = AiAssistantService()
