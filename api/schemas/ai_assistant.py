"""Schemas for the AI assistant endpoints (owner management, public widget config and chat)."""

from datetime import datetime

from pydantic import BaseModel, Field


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
    created_at: datetime


class AiAssistantListResponse(BaseModel):
    """The caller's assistants."""

    assistants: list[AiAssistantResponse] = Field(default_factory=list)


class AiAssistantPublicResponse(BaseModel):
    """The configuration the chat widget needs to render itself for a prospect's assistant."""

    slug: str
    business_name: str
    assistant_name: str
    languages: list[str] = Field(default_factory=list)
    accent_color: str | None = None
    status: str


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
