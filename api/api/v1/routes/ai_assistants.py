"""AI assistant routes: owner generation/management, and public widget config + grounded chat."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant import (
    AiAssistantChatRequest,
    AiAssistantChatResponse,
    AiAssistantCreateRequest,
    AiAssistantLeadRequest,
    AiAssistantLeadResponse,
    AiAssistantListResponse,
    AiAssistantPublicResponse,
    AiAssistantResponse,
)
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.chat_service import ai_assistant_chat_service
from services.auth_service import get_current_active_user
from services.notification_service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistants"])

# Cap the history a public caller may submit, before the chat service bounds it further.
_MAX_INCOMING_MESSAGES = 40


def _demo_url(slug: str) -> str:
    base = settings.demo_host_base_url.rstrip("/")
    return f"{base}/a/{slug}"


def _accent_color(knowledge: dict[str, Any] | None) -> str | None:
    palette = (knowledge or {}).get("palette")
    return palette.get("accent") if isinstance(palette, dict) else None


def _to_owner_response(assistant: AiAssistant) -> AiAssistantResponse:
    return AiAssistantResponse(
        id=assistant.id,
        slug=assistant.slug,
        prospect_id=assistant.prospect_id,
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        languages=assistant.languages or [],
        status=assistant.status,
        demo_url=_demo_url(assistant.slug),
        created_at=assistant.created_at,
    )


@router.post("", response_model=AiAssistantResponse, status_code=status.HTTP_201_CREATED)
async def create_assistant(
    payload: AiAssistantCreateRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Generate an assistant for one of the caller's prospects."""
    prospect = db.query(ProspectDB).filter(ProspectDB.id == payload.prospect_id, ProspectDB.user_id == user.id).first()
    if not prospect:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prospect not found")
    assistant = await ai_assistant_service.create_for_prospect(db, user_id=user.id, prospect=prospect)
    return _to_owner_response(assistant)


@router.get("", response_model=AiAssistantListResponse)
async def list_assistants(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantListResponse:
    """List the caller's assistants, newest first."""
    assistants = (
        db.query(AiAssistant)
        .filter(AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
        .order_by(AiAssistant.created_at.desc())
        .all()
    )
    return AiAssistantListResponse(assistants=[_to_owner_response(assistant) for assistant in assistants])


@router.delete("/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """Soft-delete one of the caller's assistants."""
    assistant = (
        db.query(AiAssistant)
        .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
        .first()
    )
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    assistant.status = AiAssistantStatus.DELETED.value
    assistant.deleted_at = datetime.utcnow()
    db.commit()


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


@router.post("/public/{slug}/lead", response_model=AiAssistantLeadResponse, status_code=status.HTTP_201_CREATED)
async def submit_assistant_lead(
    slug: str,
    payload: AiAssistantLeadRequest,
    db: Session = Depends(get_db),
) -> AiAssistantLeadResponse:
    """Record a lead a visitor left through the assistant, then notify the owner."""
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found or inactive")
    if not payload.name.strip() or not payload.contact.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name and contact are required")

    try:
        ai_assistant_service.record_lead(
            db,
            assistant=assistant,
            name=payload.name,
            contact=payload.contact,
            need=payload.need,
            language=payload.language,
        )
    except Exception:
        # Losing the durable row must not swallow the strongest signal — still notify the owner.
        db.rollback()
        logger.warning("assistant lead persist failed (slug=%s)", slug)

    await notification_service.notify_assistant_lead(
        db,
        user_id=assistant.user_id,
        prospect_id=assistant.prospect_id,
        fallback_name=assistant.business_name,
        lead_name=payload.name.strip(),
        need=payload.need or "",
    )
    return AiAssistantLeadResponse(ok=True)
