"""AI assistant model for prospect-generated conversational receptionists."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from enums.ai_assistant_status import AiAssistantStatus

if TYPE_CHECKING:
    from models.user import User


class AiAssistant(Base):
    """
    A conversational AI receptionist generated for a prospect.

    Same engine as demo sites (one generated deliverable per prospect, shown as a
    live demo, sold), but the product is a multilingual assistant embedded on the
    prospect's own website. ``knowledge_json`` is grounded strictly on the prospect's
    enriched data — the assistant answers only from it. No Storyblok CMS here.
    """

    __tablename__ = "ai_assistants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Display name of the assistant persona shown to visitors (e.g. "Sofia").
    assistant_name: Mapped[str] = mapped_column(String(64), nullable=False, default="Sofia")
    # Active languages the assistant answers in, as ISO codes (e.g. ["fr", "en", "de"]).
    # The model detects and replies in the visitor's language; this only bounds the offer.
    languages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Optional persona tone hint injected into the system prompt (e.g. "chaleureux, concis").
    tone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AiAssistantStatus.PENDING.value,
        index=True,
    )
    # Knowledge base + persona + palette rendered publicly and fed to the model, exactly like
    # ``DemoSite.content_json``: the source of truth. Built from the prospect enrichment.
    knowledge_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Whether the widget accent is pulled from the prospect's logo (True) or kept neutral (False).
    use_brand_color: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    demo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Client website where the assistant is embedded once sold (e.g. agence-luma.lu).
    custom_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    verification_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When the demo link was first emailed to the prospect — NULL until then (TTL not started).
    demo_link_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Countdown end, set from ``demo_link_sent_at``; NULL while the link has not been sent.
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)
    # Prospection video (webcam speech + a recording of the widget answering) — its own pipeline,
    # distinct from the site video. NULL when no video was ever requested for this assistant.
    video_status: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    video_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_generated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=datetime.utcnow, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="ai_assistants")

    def __repr__(self) -> str:
        return f"<AiAssistant id={self.id} slug={self.slug} status={self.status}>"
