"""AI assistant routes: owner generation/management, and public widget config + grounded chat."""

import logging
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from core.config import settings
from core.database import get_db
from enums.ai_assistant_photo import AiAssistantPhotoRejection
from enums.ai_assistant_request import AiAssistantRequestStatus, AiAssistantRequestType
from enums.ai_assistant_status import AiAssistantStatus
from enums.assistant_visitor_channel import AssistantVisitorChannel
from enums.demo_video_status import DemoVideoStatus
from models.ai_assistant import AiAssistant
from models.ai_assistant_lead import AiAssistantLead
from models.ai_assistant_request import AiAssistantRequest
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant import (
    AiAssistantAlertSettings,
    AiAssistantAppointmentDay,
    AiAssistantAppointmentSlotsResponse,
    AiAssistantAppointmentTime,
    AiAssistantChatRequest,
    AiAssistantChatResponse,
    AiAssistantConversationItem,
    AiAssistantConversationMessageItem,
    AiAssistantConversationsResponse,
    AiAssistantCreateRequest,
    AiAssistantInterestRequest,
    AiAssistantLeadItem,
    AiAssistantLeadRequest,
    AiAssistantLeadResponse,
    AiAssistantLeadsResponse,
    AiAssistantListResponse,
    AiAssistantPhotoResponse,
    AiAssistantPublicResponse,
    AiAssistantRequestItem,
    AiAssistantRequestsResponse,
    AiAssistantRequestUpdateRequest,
    AiAssistantResponse,
    AiAssistantUpdateRequest,
    AssistantSubscriptionItem,
    AssistantSubscriptionListResponse,
)
from schemas.ai_assistant_client_space import AiAssistantClientLinkRequest, AiAssistantClientLinkResponse
from services.ai_assistant.appointment_notices import ai_assistant_appointment_notices
from services.ai_assistant.appointment_slots import AiAssistantAppointmentSlots, AppointmentSlot
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.calendar_service import SlotTakenError, ai_assistant_calendar_service
from services.ai_assistant.chat_service import ai_assistant_chat_service
from services.ai_assistant.client_space_service import ai_assistant_client_space_service
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.conversation_service import ConversationCounts, ai_assistant_conversation_service
from services.ai_assistant.opening_hours import OpeningHoursCalendar
from services.ai_assistant.photo_service import (
    MAX_PHOTO_BYTES,
    MAX_PHOTOS_PER_SESSION,
    PhotoRejectedError,
    ai_assistant_photo_service,
)
from services.ai_assistant.report_service import ai_assistant_report_service
from services.ai_assistant.request_alerts import AlertSettings
from services.ai_assistant.request_email import AiAssistantRequestEmail
from services.ai_assistant.request_links import AiAssistantRequestLinks
from services.ai_assistant.request_service import RequestCounts, ai_assistant_request_service
from services.assistant_pricing_service import AssistantPricingService
from services.assistant_subscription_service import assistant_subscription_service
from services.assistant_video_service import (
    ASSISTANT_PRESENTER_MODULE,
    assistant_video_service,
    has_ready_video,
    public_thumbnail_url,
    public_video_file_url,
    thumbnail_object_key,
    video_object_key,
    video_page_url,
)
from services.auth_service import get_current_active_user
from services.email_variables import EmailVariables
from services.notification_service import notification_service
from services.presenter_video_service import presenter_video_service
from services.r2_storage_service import r2_storage
from services.rate_limiter import (
    assistant_chat_limiter,
    assistant_lead_limiter,
    assistant_photo_limiter,
    assistant_subscribe_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistants"])

# Cap the history a public caller may submit, before the chat service bounds it further.
_MAX_INCOMING_MESSAGES = 40


def _demo_url(slug: str) -> str:
    base = settings.demo_host_base_url.rstrip("/")
    return f"{base}/ia/{slug}"


def _embed_snippet(slug: str) -> str:
    base = settings.demo_host_base_url.rstrip("/")
    return f'<script src="{base}/ai-assistant.js" data-slug="{slug}" defer></script>'


def client_ip(request: Request) -> str:
    """Best-effort visitor IP for rate limiting (honours the nginx ``X-Forwarded-For``)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _owner_public_fields(assistant: AiAssistant) -> dict[str, str | None]:
    """Owner contact shown in the « me contacter » banner (photo guarded on the R2 base)."""
    user = assistant.user
    if user is None:
        return {}
    fields: dict[str, str | None] = {
        "owner_name": user.name,
        "owner_contact_phone": user.contact_phone,
        "owner_contact_email": user.contact_email,
    }
    if user.profile_photo_path and (settings.r2_public_base_url or "").strip():
        fields["owner_profile_photo_url"] = r2_storage.public_url(user.profile_photo_path)
    return fields


def _to_owner_response(
    assistant: AiAssistant,
    subscription: object | None = None,
    conversations: ConversationCounts | None = None,
    requests: RequestCounts | None = None,
) -> AiAssistantResponse:
    return AiAssistantResponse(
        id=assistant.id,
        slug=assistant.slug,
        prospect_id=assistant.prospect_id,
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        languages=assistant.languages or [],
        tone=assistant.tone,
        accent_color=ai_assistant_service.accent_color(assistant),
        use_brand_color=assistant.use_brand_color,
        status=assistant.status,
        demo_url=_demo_url(assistant.slug),
        embed_snippet=_embed_snippet(assistant.slug),
        demo_link_sent_at=assistant.demo_link_sent_at,
        expires_at=assistant.expires_at,
        video_status=assistant.video_status,
        video_page_url=video_page_url(assistant.slug) if has_ready_video(assistant) else None,
        video_error=assistant.video_error,
        subscription_status=getattr(subscription, "status", None),
        subscription_amount_cents=getattr(subscription, "amount_cents", None),
        subscription_interval=getattr(subscription, "interval", None),
        conversations_7d=conversations.last_7_days if conversations else 0,
        conversations_30d=conversations.last_30_days if conversations else 0,
        requests_7d=requests.last_7_days if requests else 0,
        requests_30d=requests.last_30_days if requests else 0,
        requests_outside_hours_pct=requests.outside_hours_pct if requests else None,
        churn_risk=ai_assistant_report_service.is_churn_risk(
            status=assistant.status,
            subscribed_at=getattr(subscription, "activated_at", None) or getattr(subscription, "created_at", None),
            conversations_30d=conversations.last_30_days if conversations else 0,
            requests_30d=requests.last_30_days if requests else 0,
        ),
        alerts=_alert_settings(assistant),
        eu_only=bool(assistant.eu_only),
        created_at=assistant.created_at,
    )


def _to_full_owner_response(db: Session, assistant: AiAssistant) -> AiAssistantResponse:
    """One assistant as the list shows it (subscription and counts included), after an edit."""
    return _to_owner_response(
        assistant,
        assistant_subscription_service.active_by_assistant_ids(db, [assistant.id]).get(assistant.id),
        ai_assistant_conversation_service.counts_for_assistants(db, [assistant.id]).get(assistant.id),
        ai_assistant_request_service.counts_for_assistants(db, [assistant.id]).get(assistant.id),
    )


def _alert_settings(assistant: AiAssistant) -> AiAssistantAlertSettings:
    settings = AlertSettings.of(assistant)
    return AiAssistantAlertSettings(
        phone=settings.phone_e164,
        sms_enabled=settings.sms_enabled,
        email_enabled=settings.email_enabled,
        sms_types=[item for item in AiAssistantRequestType if item in settings.sms_types],
        quiet_start_hour=settings.quiet_start_hour,
        quiet_end_hour=settings.quiet_end_hour,
    )


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
    prospect_id: int | None = None,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantListResponse:
    """List the caller's assistants, newest first (optionally filtered to one prospect)."""
    query = db.query(AiAssistant).filter(AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
    if prospect_id is not None:
        query = query.filter(AiAssistant.prospect_id == prospect_id)
    assistants = query.order_by(AiAssistant.created_at.desc()).all()
    subscriptions = assistant_subscription_service.active_by_assistant_ids(db, [a.id for a in assistants])
    conversation_counts = ai_assistant_conversation_service.counts_for_assistants(db, [a.id for a in assistants])
    request_counts = ai_assistant_request_service.counts_for_assistants(db, [a.id for a in assistants])
    return AiAssistantListResponse(
        assistants=[
            _to_owner_response(
                assistant,
                subscriptions.get(assistant.id),
                conversation_counts.get(assistant.id),
                request_counts.get(assistant.id),
            )
            for assistant in assistants
        ]
    )


@router.get("/{assistant_id}/conversations", response_model=AiAssistantConversationsResponse)
async def list_assistant_conversations(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantConversationsResponse:
    """The latest conversations visitors had with one of the caller's assistants (read-only journal)."""
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)
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
                        id=message.id, role=message.role, content=message.content, created_at=message.created_at
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
    booked = ai_assistant_calendar_service.booked_labels(db, [request.id for request, _name in rows])
    return AiAssistantRequestsResponse(
        requests=[_to_request_item(request, business_name, booked.get(request.id)) for request, business_name in rows],
        pending_count=ai_assistant_request_service.pending_count(db, user.id),
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
    booked = ai_assistant_calendar_service.booked_labels(db, [updated.id]).get(updated.id)
    return _to_request_item(updated, assistant.business_name if assistant else "", booked)


def _to_subscription_item(
    subscription: object, business_name: str | None, assistant_name: str | None
) -> AssistantSubscriptionItem:
    """Build the API item from a subscription row + its assistant's names."""
    return AssistantSubscriptionItem(
        id=subscription.id,
        ai_assistant_id=subscription.ai_assistant_id,
        prospect_id=subscription.prospect_id,
        business_name=business_name,
        assistant_name=assistant_name,
        client_name=subscription.client_name,
        client_email=subscription.client_email,
        interval=subscription.interval,
        amount_cents=subscription.amount_cents,
        currency=subscription.currency,
        status=subscription.status,
        current_period_end=subscription.current_period_end,
        canceled_at=subscription.canceled_at,
        stripe_subscription_id=subscription.stripe_subscription_id,
        created_at=subscription.created_at,
    )


@router.get("/subscriptions", response_model=AssistantSubscriptionListResponse)
async def list_assistant_subscriptions(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AssistantSubscriptionListResponse:
    """List the caller's assistant subscriptions + the headline KPIs (active count, MRR)."""
    rows = assistant_subscription_service.list_for_user(db, user.id)
    active_count, mrr_cents = assistant_subscription_service.stats_for_user(db, user.id)
    return AssistantSubscriptionListResponse(
        subscriptions=[
            _to_subscription_item(subscription, business_name, assistant_name)
            for subscription, business_name, assistant_name in rows
        ],
        active_count=active_count,
        mrr_cents=mrr_cents,
    )


@router.post("/subscriptions/{subscription_id}/cancel", response_model=AssistantSubscriptionItem)
async def cancel_assistant_subscription(
    subscription_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AssistantSubscriptionItem:
    """Cancel one of the caller's subscriptions (immediately, on Stripe + locally)."""
    subscription = assistant_subscription_service.get_owned(db, subscription_id, user.id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement introuvable.")
    try:
        assistant_subscription_service.cancel(db, subscription)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Assistant subscription cancel failed for %s", subscription_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe indisponible pour annuler."
        ) from exc
    assistant = db.get(AiAssistant, subscription.ai_assistant_id) if subscription.ai_assistant_id else None
    return _to_subscription_item(
        subscription, getattr(assistant, "business_name", None), getattr(assistant, "assistant_name", None)
    )


@router.post("/subscriptions/{subscription_id}/refund", status_code=status.HTTP_204_NO_CONTENT)
async def refund_assistant_subscription(
    subscription_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """Refund the subscription's latest payment (« satisfait-remboursé »)."""
    subscription = assistant_subscription_service.get_owned(db, subscription_id, user.id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement introuvable.")
    try:
        assistant_subscription_service.refund_last_payment(db, subscription)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Assistant subscription refund failed for %s", subscription_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe indisponible pour rembourser."
        ) from exc


@router.patch("/{assistant_id}", response_model=AiAssistantResponse)
async def update_assistant(
    assistant_id: int,
    payload: AiAssistantUpdateRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Edit one of the caller's assistants (name, persona, languages, accent, owner alerts, EU only)."""
    assistant = (
        db.query(AiAssistant)
        .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
        .first()
    )
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    try:
        updated = ai_assistant_service.update(db, assistant, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _to_full_owner_response(db, updated)


@router.post("/{assistant_id}/regenerate", response_model=AiAssistantResponse)
async def regenerate_assistant(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Rebuild an assistant's knowledge from its prospect's latest data (branding and persona kept)."""
    assistant = (
        db.query(AiAssistant)
        .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
        .first()
    )
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    if assistant.prospect_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This assistant has no prospect to regenerate from"
        )
    prospect = (
        db.query(ProspectDB).filter(ProspectDB.id == assistant.prospect_id, ProspectDB.user_id == user.id).first()
    )
    if not prospect:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Prospect not found for this assistant")
    updated = await ai_assistant_service.regenerate_for_prospect(db, assistant=assistant, prospect=prospect)
    return _to_full_owner_response(db, updated)


def _owned_assistant_or_404(db: Session, assistant_id: int, user_id: int) -> AiAssistant:
    """Fetch a caller-owned, non-deleted assistant, or raise 404."""
    assistant = (
        db.query(AiAssistant)
        .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user_id, AiAssistant.deleted_at.is_(None))
        .first()
    )
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    return assistant


@router.post("/{assistant_id}/client-link", response_model=AiAssistantClientLinkResponse)
async def issue_assistant_client_link(
    assistant_id: int,
    payload: AiAssistantClientLinkRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantClientLinkResponse:
    """A fresh client-space link for one of the caller's sold assistants, emailed to the business on demand."""
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)
    if assistant.status != AiAssistantStatus.DELIVERED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="L'espace client s'ouvre une fois l'assistant vendu."
        )
    delivery = await ai_assistant_client_space_service.issue_link(db, assistant, send=payload.send)
    return AiAssistantClientLinkResponse(
        url=delivery.url, expires_at=delivery.expires_at, sent_to=delivery.sent_to, send_error=delivery.send_error
    )


@router.post("/{assistant_id}/video", response_model=AiAssistantResponse)
async def generate_assistant_video(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Start generating the assistant's prospection video (webcam speech + a recording of the widget)."""
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)
    try:
        assistant_video_service.request_generation(db, assistant, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _to_full_owner_response(db, assistant)


@router.get("/{assistant_id}/video-context")
async def get_assistant_video_context(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Everything the desktop sidecar needs to render this assistant's video locally.

    Unlike the site — whose editor sequence needs the owner's Storyblok session, forcing a desktop
    build — the assistant video has no such dependency; the desktop path is preferred only to spare
    the shared VPS. The sidecar records the public widget answering, montages it with its bundled
    ffmpeg, and posts the finished clip back via ``POST /{id}/video-final``.
    """
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)
    if assistant.status != AiAssistantStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La vidéo ne peut être générée que pour un assistant actif.",
        )
    presenter = presenter_video_service.get_for_user(db, user.id, ASSISTANT_PRESENTER_MODULE)
    if presenter is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun clip de présentation « assistant » enregistré.",
        )
    total_seconds = presenter.duration_seconds - presenter.intro_seconds - presenter.outro_seconds
    first_name: str | None = None
    if assistant.prospect_id:
        resolved_first, _last, _gender = EmailVariables.resolved_contact(db, assistant.prospect_id)
        first_name = resolved_first or None
    return {
        "slug": assistant.slug,
        "demo_url": _demo_url(assistant.slug),
        "first_name": first_name,
        "presenter_duration": presenter.duration_seconds,
        "presenter_intro": presenter.intro_seconds,
        "presenter_outro": presenter.outro_seconds,
        "total_seconds": round(total_seconds, 2),
        "out_width": 1280,
        "out_height": 720,
        "fps": 30,
    }


@router.post("/{assistant_id}/video-final", response_model=AiAssistantResponse)
async def upload_assistant_video_final(
    assistant_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """
    Store a desktop-produced FINAL assistant video and mark it ready.

    The sidecar montages the whole clip locally and returns a zip (``video.mp4`` + ``thumbnail.jpg``);
    here we push both to R2 and flip the status — the VPS never touches ffmpeg for a desktop build.
    """
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)

    work_dir = Path(tempfile.mkdtemp(prefix=f"assistant-video-final-{assistant.slug}-"))
    try:
        zip_path = work_dir / "bundle.zip"
        with zip_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        video_path = work_dir / "video.mp4"
        thumbnail_path = work_dir / "thumbnail.jpg"
        try:
            with zipfile.ZipFile(zip_path) as archive:
                video_path.write_bytes(archive.read("video.mp4"))
                thumbnail_path.write_bytes(archive.read("thumbnail.jpg"))
        except (zipfile.BadZipFile, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Archive vidéo invalide (video.mp4 + thumbnail.jpg attendus).",
            ) from exc

        await r2_storage.upload_file_async(video_path, video_object_key(assistant.slug), "video/mp4")
        await r2_storage.upload_file_async(thumbnail_path, thumbnail_object_key(assistant.slug), "image/jpeg")
        assistant.video_status = DemoVideoStatus.READY.value
        assistant.video_error = None
        assistant.video_generated_at = datetime.now(UTC)
        db.commit()
        db.refresh(assistant)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    return _to_full_owner_response(db, assistant)


@router.delete("/{assistant_id}/video", response_model=AiAssistantResponse)
async def clear_assistant_video(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Delete the assistant's generated video and reset its state."""
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)
    assistant_video_service.clear_video(db, assistant)
    return _to_full_owner_response(db, assistant)


@router.get("/{assistant_id}/subscription/link")
async def get_assistant_subscription_link(
    assistant_id: int,
    interval: str = "month",
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    The permanent subscription link (monthly or annual) the owner sends to the client.

    It never expires: each click opens a fresh Stripe Checkout on the public ``subscribe`` endpoint,
    at the price configured at that moment (locked once the client pays).
    """
    assistant = _owned_assistant_or_404(db, assistant_id, user.id)
    if assistant.status == AiAssistantStatus.DELIVERED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cet assistant est déjà vendu.")
    if assistant.status not in (AiAssistantStatus.ACTIVE.value, AiAssistantStatus.EXPIRED.value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="L'assistant doit être actif.")
    if interval not in ("month", "year"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Intervalle invalide (month ou year).")
    return {"url": assistant_subscription_service.subscription_link(assistant, interval)}


@router.get("/public/{slug}/subscribe")
async def subscribe_to_assistant(
    slug: str,
    request: Request,
    interval: str = "month",
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Open a fresh Stripe Checkout for a client clicking the permanent subscription link.

    A live or expired demo can be subscribed to (the payment revives an expired one); an assistant
    already sold sends the client to its page instead of a second checkout.
    """
    if not assistant_subscribe_limiter.allow(f"{slug}:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de tentatives, réessayez plus tard"
        )
    assistant = ai_assistant_service.get_by_slug(db, slug)
    if assistant is None or assistant.status not in (
        AiAssistantStatus.ACTIVE.value,
        AiAssistantStatus.EXPIRED.value,
        AiAssistantStatus.DELIVERED.value,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    if assistant.status == AiAssistantStatus.DELIVERED.value:
        return RedirectResponse(url=_demo_url(assistant.slug), status_code=status.HTTP_303_SEE_OTHER)
    if interval not in ("month", "year"):
        interval = "month"
    try:
        checkout_url = assistant_subscription_service.create_checkout_session(
            db,
            user_id=assistant.user_id,
            assistant=assistant,
            interval=interval,
            success_url=f"{_demo_url(assistant.slug)}?subscribed=1",
            cancel_url=_demo_url(assistant.slug),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Assistant subscription checkout failed for slug %s", slug)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe indisponible pour le moment."
        ) from exc
    return RedirectResponse(url=checkout_url, status_code=status.HTTP_303_SEE_OTHER)


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
    video_ready = has_ready_video(assistant)
    return AiAssistantPublicResponse(
        slug=assistant.slug,
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        assistant_gender=ai_assistant_config_builder.resolve_persona_gender(assistant.assistant_name).value,
        languages=assistant.languages or [],
        accent_color=ai_assistant_service.accent_color(assistant),
        status=assistant.status,
        **_owner_public_fields(assistant),
        video_available=video_ready,
        video_url=public_video_file_url(assistant.slug) if video_ready else None,
        video_thumbnail_url=public_thumbnail_url(assistant.slug, assistant.video_generated_at) if video_ready else None,
        monthly_price_label=(
            AssistantPricingService.format_price(AssistantPricingService.monthly_price_cents(db, assistant.user_id))
            if assistant.status == AiAssistantStatus.ACTIVE.value
            else None
        ),
    )


@router.post("/public/{slug}/chat", response_model=AiAssistantChatResponse)
async def chat_with_assistant(
    slug: str,
    payload: AiAssistantChatRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AiAssistantChatResponse:
    """Answer a visitor's message as the prospect's grounded assistant."""
    if not assistant_chat_limiter.allow(f"{slug}:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de messages, réessayez plus tard"
        )
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
        eu_only=bool(assistant.eu_only),
    )
    # The journal must never cost the visitor their answer.
    try:
        ai_assistant_conversation_service.record_turn(
            db,
            assistant=assistant,
            session_id=payload.session_id,
            language=payload.language,
            visitor_message=history[-1]["content"],
            reply=reply,
            is_test=payload.internal,
        )
    except Exception:
        logger.warning("Assistant conversation journal failed for slug %s", slug, exc_info=True)
    return AiAssistantChatResponse(
        reply=reply, offer_booking=ai_assistant_chat_service.asks_for_appointment(history[-1]["content"])
    )


@router.get("/public/{slug}/appointment-slots", response_model=AiAssistantAppointmentSlotsResponse)
async def get_assistant_appointment_slots(
    slug: str,
    request: Request,
    after: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AiAssistantAppointmentSlotsResponse:
    """What the appointment panel offers: the agenda's next free slots (3 at a time), else open half-days."""
    if not assistant_chat_limiter.allow(f"slots:{slug}:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de demandes, réessayez plus tard"
        )
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found or inactive")
    offer = await ai_assistant_calendar_service.offer(db, assistant, after=after)
    if offer.slots is not None and offer.settings is not None:
        return AiAssistantAppointmentSlotsResponse(
            mode=offer.mode,
            max_chosen=1,
            times=[AiAssistantAppointmentTime(start=slot.start, end=slot.end) for slot in offer.slots.slots],
            has_more=offer.slots.has_more,
            types=list(offer.settings.appointment_types),
            duration_minutes=offer.settings.duration_minutes,
        )
    return AiAssistantAppointmentSlotsResponse(
        mode=offer.mode,
        days=[AiAssistantAppointmentDay(date=item.day, periods=list(item.periods)) for item in offer.days],
        max_chosen=AiAssistantAppointmentSlots.MAX_CHOSEN,
    )


@router.post("/public/{slug}/lead", response_model=AiAssistantLeadResponse, status_code=status.HTTP_201_CREATED)
async def submit_assistant_lead(
    slug: str,
    payload: AiAssistantLeadRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AiAssistantLeadResponse:
    """Record the request a visitor left through the assistant; typing and announcing run in the background."""
    if not assistant_lead_limiter.allow(f"{slug}:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de demandes, réessayez plus tard"
        )
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found or inactive")
    if not payload.name.strip() or not payload.contact.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name and contact are required")

    try:
        captured, _created = ai_assistant_request_service.capture(
            db,
            assistant=assistant,
            name=payload.name,
            contact=payload.contact,
            need=payload.need,
            language=payload.language,
            session_id=payload.session_id,
            is_test=payload.internal,
            appointment_slots=[AppointmentSlot(day=slot.date, period=slot.period) for slot in payload.slots],
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception:
        # Losing the durable row must not swallow the strongest signal — still notify the owner.
        db.rollback()
        logger.warning("assistant request persist failed (slug=%s)", slug, exc_info=True)
        if not payload.internal:
            await notification_service.notify_assistant_lead(
                db,
                user_id=assistant.user_id,
                prospect_id=assistant.prospect_id,
                fallback_name=assistant.business_name,
                lead_name=payload.name.strip(),
                need=payload.need or "",
            )
        return AiAssistantLeadResponse(ok=True)

    booked_start: datetime | None = None
    channel: AssistantVisitorChannel | None = None
    if payload.booking is not None:
        try:
            outcome = await ai_assistant_calendar_service.book_request(
                db, assistant, captured, start=payload.booking.start, type_label=payload.booking.type
            )
        except SlotTakenError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        if outcome.appointment is not None:
            ai_assistant_appointment_notices.schedule_confirmation(outcome.appointment.id)
            booked_start = OpeningHoursCalendar.to_business_time(outcome.appointment.starts_at)
            if outcome.appointment.visitor_phone_e164:
                channel = AssistantVisitorChannel.SMS
            elif outcome.appointment.visitor_email:
                channel = AssistantVisitorChannel.EMAIL

    ai_assistant_request_service.schedule_follow_up(captured.id)
    return AiAssistantLeadResponse(ok=True, booked_start=booked_start, confirmation_channel=channel)


# Room for the multipart envelope and the three text fields around the photo itself.
_PHOTO_REQUEST_MAX_BYTES = MAX_PHOTO_BYTES + 64 * 1024


def _photo_rejection_status(reason: AiAssistantPhotoRejection) -> int:
    """HTTP status of a refused photo."""
    if reason is AiAssistantPhotoRejection.TOO_LARGE:
        return status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    if reason is AiAssistantPhotoRejection.UNREADABLE:
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    if reason is AiAssistantPhotoRejection.QUOTA:
        return status.HTTP_409_CONFLICT
    return status.HTTP_503_SERVICE_UNAVAILABLE


@router.post("/public/{slug}/photo", response_model=AiAssistantPhotoResponse, status_code=status.HTTP_201_CREATED)
async def submit_assistant_photo(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> AiAssistantPhotoResponse:
    """A photo for a quote (multipart ``file``, ``session_id``, ``language``, ``internal``): stored,
    described by the vision model (never a price), kept for the visitor's request.

    The form is parsed by hand, after the rate limit and the declared size are checked: a public
    upload must never write an unbounded body to disk first.
    """
    if not assistant_photo_limiter.allow(f"{slug}:{client_ip(request)}"):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de photos, réessayez plus tard")
    declared_length = request.headers.get("content-length", "")
    if not declared_length.isdigit():
        raise HTTPException(status_code=status.HTTP_411_LENGTH_REQUIRED, detail="Taille de la photo inconnue")
    if int(declared_length) > _PHOTO_REQUEST_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Photo trop lourde (8 Mo maximum)."
        )
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found or inactive")
    if not r2_storage.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Envoi de photo indisponible pour le moment"
        )
    form = await request.form(max_files=1, max_fields=3)
    try:
        upload = form.get("file")
        raw_session = form.get("session_id")
        raw_language = form.get("language")
        raw_internal = form.get("internal")
        session_id = raw_session.strip()[:64] if isinstance(raw_session, str) else ""
        if not isinstance(upload, StarletteUploadFile) or not session_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Photo ou session manquante")
        data = await upload.read(MAX_PHOTO_BYTES + 1)
    finally:
        await form.close()
    try:
        photo = await ai_assistant_photo_service.receive(
            db,
            assistant=assistant,
            data=data,
            session_id=session_id,
            language=raw_language.strip()[:8] if isinstance(raw_language, str) else None,
            is_test=isinstance(raw_internal, str) and raw_internal.strip().lower() in {"true", "1"},
        )
    except PhotoRejectedError as exc:
        raise HTTPException(status_code=_photo_rejection_status(exc.reason), detail=exc.message) from exc
    # A photo sent after the contact details joins the request already left in this visit.
    if photo.relevant is not False:
        ai_assistant_request_service.attach_late_photos(db, assistant_id=assistant.id, session_id=session_id)
    kept = ai_assistant_photo_service.kept_count(db, assistant.id, session_id)
    need = " — ".join(part for part in (photo.object_label, photo.damage) if part) or None
    return AiAssistantPhotoResponse(
        accepted=photo.relevant is not False,
        reply=photo.reply or "",
        need=need,
        remaining=max(MAX_PHOTOS_PER_SESSION - kept, 0),
    )


def _handled_link_page(
    db: Session, request_id: int, exp: int, token: str | None
) -> tuple[AiAssistantRequest | None, HTMLResponse | None]:
    """Check a « marquer traitée » link; returns the request, or the error page to show instead."""
    if not AiAssistantRequestLinks.verify(request_id, exp, token):
        return None, HTMLResponse(
            AiAssistantRequestEmail.confirmation_page(
                "Lien expiré ou invalide",
                "Ce lien ne permet plus de traiter la demande. Utilisez le dernier email reçu.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    record = db.get(AiAssistantRequest, request_id)
    if record is None:
        return None, HTMLResponse(
            AiAssistantRequestEmail.confirmation_page("Demande introuvable", "Cette demande n'existe plus."),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return record, None


@router.get("/public/requests/{request_id}/handled", response_class=HTMLResponse)
async def confirm_request_handled_page(
    request_id: int,
    exp: int = 0,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """The « marquer traitée » link of the summary email: shows the request and a confirm button, changes nothing."""
    record, error_page = _handled_link_page(db, request_id, exp, token)
    if error_page is not None or record is None:
        return error_page or HTMLResponse(status_code=status.HTTP_404_NOT_FOUND)
    if record.status != AiAssistantRequestStatus.NEW.value:
        return HTMLResponse(
            AiAssistantRequestEmail.confirmation_page(
                "Demande déjà traitée", f"La demande de {record.name} n'est plus à traiter."
            )
        )
    return HTMLResponse(
        AiAssistantRequestEmail.confirmation_page(
            f"Demande de {record.name}",
            "Vous avez répondu à cette demande ? Marquez-la comme traitée pour ne plus qu'on vous la rappelle.",
            action_label="Marquer comme traitée",
        )
    )


@router.post("/public/requests/{request_id}/handled", response_class=HTMLResponse)
async def mark_request_handled_from_email(
    request_id: int,
    exp: int = 0,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Confirm the « marquer traitée » link: a signed, expiring action, no account needed."""
    record, error_page = _handled_link_page(db, request_id, exp, token)
    if error_page is not None or record is None:
        return error_page or HTMLResponse(status_code=status.HTTP_404_NOT_FOUND)
    changed = ai_assistant_request_service.mark_handled(db, record)
    title = "Demande marquée comme traitée" if changed else "Demande déjà traitée"
    return HTMLResponse(
        AiAssistantRequestEmail.confirmation_page(
            title, f"La demande de {record.name} ne vous sera plus rappelée. Merci !"
        )
    )


@router.post("/public/{slug}/interest", status_code=status.HTTP_204_NO_CONTENT)
async def submit_assistant_interest(
    slug: str,
    payload: AiAssistantInterestRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    """The prospect raised their hand on the assistant sales page — notify the owner (hot lead)."""
    if not assistant_lead_limiter.allow(f"interest:{slug}:{client_ip(request)}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Trop de demandes, réessayez plus tard"
        )
    assistant = ai_assistant_service.get_public_by_slug(db, slug)
    if not assistant:
        return  # Unknown or inactive slug: ignore, like the public demo-events beacon.
    await notification_service.notify_assistant_interest(
        db,
        user_id=assistant.user_id,
        prospect_id=assistant.prospect_id,
        fallback_name=assistant.business_name,
        message=(payload.message or "").strip(),
    )
