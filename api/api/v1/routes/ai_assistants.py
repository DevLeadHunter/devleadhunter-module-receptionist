"""Public AI assistant routes: widget config and grounded chat, served by slug."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.ai_assistant import (
    AiAssistantChatRequest,
    AiAssistantChatResponse,
    AiAssistantPublicResponse,
)
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.chat_service import ai_assistant_chat_service

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistants"])

# Cap the history a public caller may submit, before the chat service bounds it further.
_MAX_INCOMING_MESSAGES = 40


def _accent_color(knowledge: dict[str, Any] | None) -> str | None:
    palette = (knowledge or {}).get("palette")
    return palette.get("accent") if isinstance(palette, dict) else None


@router.get("/public/{slug}", response_model=AiAssistantPublicResponse)
async def get_public_assistant(slug: str, db: Session = Depends(get_db)) -> AiAssistantPublicResponse:
    """Public config consumed by the embedded chat widget."""
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found or inactive")
    return AiAssistantPublicResponse(
        slug=assistant.slug,
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        languages=assistant.languages or [],
        accent_color=_accent_color(assistant.knowledge_json),
        status=assistant.status,
    )


@router.post("/public/{slug}/chat", response_model=AiAssistantChatResponse)
async def chat_with_assistant(
    slug: str,
    payload: AiAssistantChatRequest,
    db: Session = Depends(get_db),
) -> AiAssistantChatResponse:
    """Answer a visitor's message as the prospect's grounded assistant."""
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found or inactive")
    if not payload.messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No message to answer")

    history = [
        {"role": message.role, "content": message.content} for message in payload.messages[-_MAX_INCOMING_MESSAGES:]
    ]
    reply = await ai_assistant_chat_service.answer(
        knowledge=assistant.knowledge_json or {},
        assistant_name=assistant.assistant_name,
        languages=assistant.languages,
        tone=assistant.tone,
        history=history,
    )
    return AiAssistantChatResponse(reply=reply)
