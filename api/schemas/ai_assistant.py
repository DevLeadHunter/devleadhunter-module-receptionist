"""Schemas for the AI assistant endpoints (owner management, public widget config and chat)."""

from datetime import datetime

from pydantic import BaseModel, Field

from enums.ai_assistant_persona_gender import AiAssistantPersonaGender


class AiAssistantCreateRequest(BaseModel):
    """Request to generate an assistant for one of the caller's prospects."""

    prospect_id: int


class AiAssistantUpdateRequest(BaseModel):
    """Owner edits to an assistant's branding and persona (all optional, partial update)."""

    assistant_name: str | None = None
    business_name: str | None = None
    languages: list[str] | None = None
    tone: str | None = None
    use_brand_color: bool | None = None
    accent_color: str | None = None


class AiAssistantResponse(BaseModel):
    """An assistant as seen by its owner in the dashboard."""

    id: int
    slug: str
    prospect_id: int | None = None
    business_name: str
    assistant_name: str
    languages: list[str] = Field(default_factory=list)
    tone: str | None = None
    accent_color: str | None = None
    use_brand_color: bool = True
    status: str
    demo_url: str
    embed_snippet: str
    # Demo countdown: NULL until the link is first emailed or texted, then the expiry it set.
    demo_link_sent_at: datetime | None = None
    expires_at: datetime | None = None
    # Prospection video state: NULL when never requested, else pending/generating/ready/failed.
    video_status: str | None = None
    video_page_url: str | None = None
    video_error: str | None = None
    # Subscription state: NULL when no active subscription, else the locked plan the client pays.
    subscription_status: str | None = None
    subscription_amount_cents: int | None = None
    subscription_interval: str | None = None
    created_at: datetime


class AiAssistantListResponse(BaseModel):
    """The caller's assistants."""

    assistants: list[AiAssistantResponse] = Field(default_factory=list)


class AssistantSubscriptionItem(BaseModel):
    """One assistant subscription, as the Ventes/Abonnements page shows it."""

    id: int
    ai_assistant_id: int | None = None
    prospect_id: int | None = None
    business_name: str | None = None
    assistant_name: str | None = None
    client_name: str | None = None
    client_email: str | None = None
    interval: str
    amount_cents: int
    currency: str
    status: str
    current_period_end: datetime | None = None
    canceled_at: datetime | None = None
    stripe_subscription_id: str | None = None
    created_at: datetime


class AssistantSubscriptionListResponse(BaseModel):
    """The caller's subscriptions plus the headline KPIs (active count + MRR)."""

    subscriptions: list[AssistantSubscriptionItem] = Field(default_factory=list)
    active_count: int = 0
    mrr_cents: int = 0


class AiAssistantPublicResponse(BaseModel):
    """The configuration the chat widget needs to render itself for a prospect's assistant."""

    slug: str
    business_name: str
    assistant_name: str
    assistant_gender: str = AiAssistantPersonaGender.FEMININE.value
    languages: list[str] = Field(default_factory=list)
    accent_color: str | None = None
    status: str
    # Owner contact, shown in the « me contacter » banner so the prospect can reach the seller.
    owner_name: str | None = None
    owner_profile_photo_url: str | None = None
    owner_contact_phone: str | None = None
    owner_contact_email: str | None = None
    # Prospection video (the /va/{slug} player + email thumbnail), present only when generated.
    video_available: bool = False
    video_url: str | None = None
    video_thumbnail_url: str | None = None


class AiAssistantInterestRequest(BaseModel):
    """A prospect raising their hand from the assistant sales page (« me contacter » banner)."""

    message: str | None = Field(None, max_length=2000)


class AiAssistantChatMessage(BaseModel):
    """A single conversation turn from the widget."""

    role: str
    content: str


class AiAssistantChatRequest(BaseModel):
    """A visitor's chat request: the conversation so far, ending on the visitor's message."""

    messages: list[AiAssistantChatMessage] = Field(default_factory=list)


class AiAssistantChatResponse(BaseModel):
    """The assistant's reply to a chat request."""

    reply: str


class AiAssistantLeadRequest(BaseModel):
    """A lead a visitor submits through the assistant widget."""

    name: str
    contact: str
    need: str | None = None
    language: str | None = None


class AiAssistantLeadResponse(BaseModel):
    """Acknowledgement that a lead was recorded."""

    ok: bool


class AiAssistantLeadItem(BaseModel):
    """One lead captured by an assistant, for the owner's leads list."""

    id: int
    assistant_id: int
    prospect_id: int | None = None
    business_name: str
    name: str
    contact: str
    need: str | None = None
    language: str | None = None
    created_at: datetime


class AiAssistantLeadsResponse(BaseModel):
    """The leads captured across the caller's assistants, newest first."""

    leads: list[AiAssistantLeadItem] = Field(default_factory=list)
