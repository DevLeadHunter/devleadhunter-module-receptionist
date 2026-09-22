"""Schemas for the public AI assistant endpoints (widget config and chat)."""

from pydantic import BaseModel, Field


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
