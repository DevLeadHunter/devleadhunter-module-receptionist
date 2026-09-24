"""Generate and serve a prospect's AI assistant.

Mirrors the demo-site engine: one assistant generated per prospect, from the same enrichment, served
publicly by slug and answering visitors. No Storyblok — the assistant renders from ``knowledge_json``.
"""

import re
import unicodedata
from typing import Any

from sqlalchemy.orm import Session

from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_lead import AiAssistantLead
from models.prospect_db import ProspectDB
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.knowledge_builder import ai_assistant_knowledge_builder
from services.enrichment_service import enrichment_service

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
    ) -> dict[str, Any]:
        """Assemble the persistable fields of an assistant from a prospect's data (pure, no DB).

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
        """Apply owner edits (branding/persona) to an assistant, then persist.

        Only keys present in ``fields`` are touched, so a partial edit never wipes the rest.
        The accent lives in ``knowledge_json['palette']``, reassigned as a new dict so SQLAlchemy
        detects the JSON change. An empty string clears a value (neutral accent, default persona).

        Args:
            db: Active database session.
            assistant: The row to edit.
            fields: The provided fields (from ``model_dump(exclude_unset=True)``).

        Returns:
            The refreshed assistant row.
        """
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

        return assistant

    async def create_for_prospect(self, db: Session, *, user_id: int, prospect: ProspectDB) -> AiAssistant:
        """Generate an assistant for a prospect, enriching it first when needed."""
        enrichment = enrichment_service.to_dict(await enrichment_service.ensure_enriched(db, user_id, prospect))
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
        )

    def regenerate(
        self, db: Session, *, assistant: AiAssistant, prospect: ProspectDB, enrichment: dict[str, Any] | None
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
        )
        knowledge = fields["knowledge_json"]
        knowledge["palette"] = {"accent": existing_accent}
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
        """Re-enrich the prospect, then rebuild the assistant's knowledge from it (keeps branding)."""
        enrichment = enrichment_service.to_dict(
            await enrichment_service.ensure_enriched(db, assistant.user_id, prospect)
        )
        return self.regenerate(db, assistant=assistant, prospect=prospect, enrichment=enrichment)

    def record_lead(
        self,
        db: Session,
        *,
        assistant: AiAssistant,
        name: str,
        contact: str,
        need: str | None = None,
        language: str | None = None,
    ) -> AiAssistantLead:
        """Persist a lead a visitor left through an assistant, attached to its prospect."""
        lead = AiAssistantLead(
            user_id=assistant.user_id,
            prospect_id=assistant.prospect_id,
            assistant_id=assistant.id,
            name=name.strip(),
            contact=contact.strip(),
            need=(need or "").strip() or None,
            language=(language or "").strip() or None,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead

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
