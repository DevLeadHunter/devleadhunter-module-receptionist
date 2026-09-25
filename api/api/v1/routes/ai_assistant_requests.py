"""Owner routes of the requests an assistant captured and of its conversation journal, and the signed « marquer
traitée » link of the summary email.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from api.v1.routes.ai_assistant_common import (
    client_ip,
    confirmation_response,
    owned_assistant_or_404,
)
from core.database import get_db
from enums.ai_assistant_request import AiAssistantRequestStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_lead import AiAssistantLead
from models.ai_assistant_request import AiAssistantRequest
from models.user import User
from schemas.ai_assistant import (
    AiAssistantConversationItem,
    AiAssistantConversationMessageItem,
    AiAssistantConversationsResponse,
    AiAssistantLeadItem,
    AiAssistantLeadsResponse,
    AiAssistantRequestDetail,
    AiAssistantRequestItem,
    AiAssistantRequestsResponse,
    AiAssistantRequestUpdateRequest,
    AiAssistantTranscriptLine,
)
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots
from services.ai_assistant.calendar_booking import ai_assistant_calendar_booking
from services.ai_assistant.conversation_service import ai_assistant_conversation_service
from services.ai_assistant.request_links import AiAssistantRequestLinks
from services.ai_assistant.request_service import ai_assistant_request_service
from services.auth_service import get_current_active_user
from services.rate_limiter import (
    assistant_request_link_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistant-requests"])


def _to_request_item(
    request: AiAssistantRequest, business_name: str, booked: str | None = None
) -> AiAssistantRequestItem:
    return AiAssistantRequestItem(
        id=request.id,
        assistant_id=request.assistant_id,
        prospect_id=request.prospect_id,
        business_name=business_name,
        type=request.type,
        status=request.status,
        channel=request.channel,
        name=request.name,
        contact=request.contact,
        need=request.need,
        need_summary=request.need_summary,
        language=request.language,
        received_outside_hours=request.received_outside_hours,
        is_test=request.is_test,
        owner_note=request.owner_note,
        photo_urls=ai_assistant_request_service.photo_urls(request),
        appointment_slots=AiAssistantAppointmentSlots.labels(request.appointment_slots_json),
        appointment_booked=booked,
        created_at=request.created_at,
        handled_at=request.handled_at,
    )


@router.get("/{assistant_id}/conversations", response_model=AiAssistantConversationsResponse)
async def list_assistant_conversations(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantConversationsResponse:
    """The latest conversations visitors had with one of the caller's assistants (read-only journal)."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    conversations = ai_assistant_conversation_service.recent_for_assistant(db, assistant.id)
    return AiAssistantConversationsResponse(
        assistant_id=assistant.id,
        business_name=assistant.business_name,
        conversations=[
            AiAssistantConversationItem(
                id=conversation.id,
                session_id=conversation.session_id,
                language=conversation.language,
                message_count=conversation.message_count,
                started_at=conversation.started_at,
                last_message_at=conversation.last_message_at,
                messages=[
                    AiAssistantConversationMessageItem(
                        id=message.id,
                        role=message.role,
                        content=message.content,
                        photo_url=message.photo_url,
                        created_at=message.created_at,
                    )
                    for message in conversation.messages
                ],
            )
            for conversation in conversations
        ],
    )


@router.get("/leads", response_model=AiAssistantLeadsResponse)
async def list_assistant_leads(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantLeadsResponse:
    """Legacy: the leads captured before requests existed (read-only history, no longer written)."""
    rows = (
        db.query(AiAssistantLead, AiAssistant.business_name)
        .join(AiAssistant, AiAssistant.id == AiAssistantLead.assistant_id)
        .filter(AiAssistantLead.user_id == user.id)
        .order_by(AiAssistantLead.created_at.desc())
        .limit(500)
        .all()
    )
    return AiAssistantLeadsResponse(
        leads=[
            AiAssistantLeadItem(
                id=lead.id,
                assistant_id=lead.assistant_id,
                prospect_id=lead.prospect_id,
                business_name=business_name,
                name=lead.name,
                contact=lead.contact,
                need=lead.need,
                language=lead.language,
                created_at=lead.created_at,
            )
            for lead, business_name in rows
        ]
    )


@router.get("/requests", response_model=AiAssistantRequestsResponse)
async def list_assistant_requests(
    assistant_id: int | None = None,
    status_filter: AiAssistantRequestStatus | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantRequestsResponse:
    """The requests visitors left across the caller's assistants, newest first."""
    rows = ai_assistant_request_service.list_for_owner(db, user.id, assistant_id=assistant_id, status=status_filter)
    booked = ai_assistant_calendar_booking.booked_labels(db, [request.id for request, _name in rows])
    return AiAssistantRequestsResponse(
        requests=[_to_request_item(request, business_name, booked.get(request.id)) for request, business_name in rows],
        pending_count=ai_assistant_request_service.pending_count(db, user.id),
    )


@router.get("/requests/{request_id}", response_model=AiAssistantRequestDetail)
async def get_assistant_request(
    request_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantRequestDetail:
    """One of the caller's requests with the conversation it came out of."""
    record = ai_assistant_request_service.get_for_owner(db, user.id, request_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    assistant = db.get(AiAssistant, record.assistant_id)
    booked = ai_assistant_calendar_booking.booked_labels(db, [record.id]).get(record.id)
    transcript = ai_assistant_request_service.transcript(db, record)
    return AiAssistantRequestDetail(
        request=_to_request_item(record, assistant.business_name if assistant else "", booked),
        transcript=[
            AiAssistantTranscriptLine(role=line.role, content=line.content, photo_url=line.photo_url)
            for line in transcript
            if line.role in ("user", "assistant")
        ],
    )


@router.patch("/requests/{request_id}", response_model=AiAssistantRequestItem)
async def update_assistant_request(
    request_id: int,
    payload: AiAssistantRequestUpdateRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantRequestItem:
    """Mark one of the caller's requests handled / dropped / new again, or edit its note."""
    record = ai_assistant_request_service.get_for_owner(db, user.id, request_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    updated = ai_assistant_request_service.update_for_owner(
        db, record, status=payload.status, owner_note=payload.owner_note
    )
    assistant = db.get(AiAssistant, updated.assistant_id)
    booked = ai_assistant_calendar_booking.booked_labels(db, [updated.id]).get(updated.id)
    return _to_request_item(updated, assistant.business_name if assistant else "", booked)


def _resolve_handled_link(
    db: Session, request_id: int, exp: int, token: str | None
) -> AiAssistantRequest | HTMLResponse:
    """The request a « marquer traitée » link names, or the page to show instead (invalid link, unknown request)."""
    if not AiAssistantRequestLinks.verify(request_id, exp, token):
        return confirmation_response(
            "Lien expiré ou invalide",
            "Ce lien ne permet plus de traiter la demande. Utilisez le dernier email reçu.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    record = db.get(AiAssistantRequest, request_id)
    if record is None:
        return confirmation_response(
            "Demande introuvable", "Cette demande n'existe plus.", status_code=status.HTTP_404_NOT_FOUND
        )
    return record


def _too_many_link_openings(request: Request) -> HTMLResponse | None:
    """The page of a « marquer traitée » link opened too often from one address, else None."""
    if assistant_request_link_limiter.allow(f"handled:{client_ip(request)}"):
        return None
    return confirmation_response(
        "Trop de tentatives", "Réessayez dans quelques minutes.", status_code=status.HTTP_429_TOO_MANY_REQUESTS
    )


@router.get("/public/requests/{request_id}/handled", response_class=HTMLResponse)
async def confirm_request_handled_page(
    request_id: int,
    request: Request,
    exp: int = 0,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """The « marquer traitée » link of the summary email: shows the request and a confirm button, changes nothing."""
    refusal = _too_many_link_openings(request)
    if refusal is not None:
        return refusal
    record = _resolve_handled_link(db, request_id, exp, token)
    if isinstance(record, HTMLResponse):
        return record
    if record.status != AiAssistantRequestStatus.NEW.value:
        return confirmation_response("Demande déjà traitée", f"La demande de {record.name} n'est plus à traiter.")
    return confirmation_response(
        f"Demande de {record.name}",
        "Vous avez répondu à cette demande ? Marquez-la comme traitée pour ne plus qu'on vous la rappelle.",
        action_label="Marquer comme traitée",
    )


@router.post("/public/requests/{request_id}/handled", response_class=HTMLResponse)
async def mark_request_handled_from_email(
    request_id: int,
    request: Request,
    exp: int = 0,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Confirm the « marquer traitée » link: a signed, expiring action, no account needed."""
    refusal = _too_many_link_openings(request)
    if refusal is not None:
        return refusal
    record = _resolve_handled_link(db, request_id, exp, token)
    if isinstance(record, HTMLResponse):
        return record
    changed = ai_assistant_request_service.mark_handled(db, record)
    title = "Demande marquée comme traitée" if changed else "Demande déjà traitée"
    return confirmation_response(title, f"La demande de {record.name} ne vous sera plus rappelée. Merci !")
