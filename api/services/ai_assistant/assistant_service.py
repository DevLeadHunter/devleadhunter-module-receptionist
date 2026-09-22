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
from models.prospect_db import ProspectDB
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.knowledge_builder import ai_assistant_knowledge_builder
from services.enrichment_service import enrichment_service


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

    def get_public_by_slug(self, db: Session, slug: str) -> AiAssistant | None:
        """Return the active, non-deleted assistant for a public slug, or None."""
        return (
            db.query(AiAssistant)
            .filter(
                AiAssistant.slug == slug,
                AiAssistant.deleted_at.is_(None),
                AiAssistant.status == AiAssistantStatus.ACTIVE.value,
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
