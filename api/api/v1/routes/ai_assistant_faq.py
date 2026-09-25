"""Owner routes of an assistant's FAQ: the answers written for it, and the questions it could not answer."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from api.v1.routes.ai_assistant_common import faq_response, owned_assistant_or_404
from core.database import get_db
from models.user import User
from schemas.ai_assistant_faq import AiAssistantFaqEntryRequest, AiAssistantFaqResponse
from services.ai_assistant.faq_service import ai_assistant_faq_service
from services.auth_service import get_current_active_user

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistant-faq"])

_ENTRY_NOT_FOUND = "Question introuvable"


@router.get("/{assistant_id}/faq", response_model=AiAssistantFaqResponse)
async def get_assistant_faq(
    assistant_id: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> AiAssistantFaqResponse:
    """The FAQ of the assistant and the questions its visitors asked that it could not answer."""
    return faq_response(owned_assistant_or_404(db, assistant_id, user.id))


@router.post("/{assistant_id}/faq", response_model=AiAssistantFaqResponse, status_code=status.HTTP_201_CREATED)
async def add_assistant_faq_entry(
    assistant_id: int,
    payload: AiAssistantFaqEntryRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantFaqResponse:
    """Answer a question in the FAQ; the same unanswered question leaves its list."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    try:
        ai_assistant_faq_service.add_faq(db, assistant, payload.question, payload.answer)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return faq_response(assistant)


@router.put("/{assistant_id}/faq/{index}", response_model=AiAssistantFaqResponse)
async def update_assistant_faq_entry(
    assistant_id: int,
    index: int,
    payload: AiAssistantFaqEntryRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantFaqResponse:
    """Rewrite an entry of the FAQ."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    try:
        ai_assistant_faq_service.update_faq(db, assistant, index, payload.question, payload.answer)
    except IndexError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_ENTRY_NOT_FOUND) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return faq_response(assistant)


@router.delete("/{assistant_id}/faq/{index}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant_faq_entry(
    assistant_id: int, index: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> Response:
    """Remove an entry of the FAQ."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    try:
        ai_assistant_faq_service.delete_faq(db, assistant, index)
    except IndexError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_ENTRY_NOT_FOUND) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{assistant_id}/unanswered/{index}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_assistant_unanswered_question(
    assistant_id: int, index: int, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> Response:
    """Drop an unanswered question without answering it."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    try:
        ai_assistant_faq_service.dismiss_unanswered(db, assistant, index)
    except IndexError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_ENTRY_NOT_FOUND) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
