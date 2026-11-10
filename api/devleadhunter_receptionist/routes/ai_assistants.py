"""Owner routes of the AI assistants: generate, list, edit, regenerate, delete, the client-space link and the
prospecting video.
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from api.v1.routes.ai_assistant_common import owned_assistant_or_404
from core.clock import naive_utc_now
from core.database import get_db
from enums.ai_assistant_request import AiAssistantRequestType
from enums.ai_assistant_start_step import AiAssistantStartStep
from enums.ai_assistant_status import AiAssistantStatus
from models.ai_assistant import AiAssistant
from models.prospect_db import ProspectDB
from models.user import User
from schemas.ai_assistant import (
    AiAssistantAlertSettings,
    AiAssistantCreateRequest,
    AiAssistantDesktopVideoRequestResponse,
    AiAssistantListResponse,
    AiAssistantResponse,
    AiAssistantUpdateRequest,
)
from schemas.ai_assistant_client_space import AiAssistantClientLinkRequest, AiAssistantClientLinkResponse
from schemas.prospection_video import ProspectionVideoDesktopFailureRequest, ProspectionVideoStateResponse
from services.activity_log_service import CATEGORY_ASSISTANT, STATUS_SUCCESS, activity_log_service
from services.ai_assistant.alert_settings import AlertSettings
from services.ai_assistant.assistant_purge import ai_assistant_purge_service
from services.ai_assistant.assistant_service import ai_assistant_service
from services.ai_assistant.avatar_service import AvatarRefusal, AvatarStorageError, ai_assistant_avatar_service
from services.ai_assistant.client_space_service import ai_assistant_client_space_service
from services.ai_assistant.config_builder import ai_assistant_config_builder
from services.ai_assistant.conversation_service import ConversationCounts, ai_assistant_conversation_service
from services.ai_assistant.embed_snippet import AiAssistantEmbedSnippet
from services.ai_assistant.faq_service import ai_assistant_faq_service
from services.ai_assistant.mailbox_service import MailboxView, ai_assistant_mailbox_service
from services.ai_assistant.report_service import ai_assistant_report_service
from services.ai_assistant.request_service import RequestCounts, ai_assistant_request_service
from services.ai_assistant.start_reminders import ai_assistant_start_reminders
from services.assistant_subscription_service import assistant_subscription_service
from services.assistant_video_service import (
    ASSISTANT_PRESENTER_MODULE,
    assistant_video_service,
    has_ready_video,
    public_thumbnail_url,
    video_page_url,
)
from services.auth_service import get_current_active_user
from services.email_variables import EmailVariables
from services.presenter_video_service import presenter_video_service
from services.prospect_search.desktop_app_presence import desktop_app_presence
from services.prospection_video_desktop_relay import assistant_video_desktop_relay
from services.prospection_video_service import ALREADY_BUILDING_MESSAGE
from services.video_pipeline import VideoGenerationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistants", tags=["ai-assistants"])


def _to_owner_response(
    assistant: AiAssistant,
    subscription: object | None = None,
    conversations: ConversationCounts | None = None,
    requests: RequestCounts | None = None,
    start_steps: list[AiAssistantStartStep] | None = None,
    mailbox: MailboxView | None = None,
    clip_in_use_since: datetime | None = None,
) -> AiAssistantResponse:
    missing_start_steps = start_steps or []
    mailbox_view = mailbox or ai_assistant_mailbox_service.view(assistant, None)
    return AiAssistantResponse(
        id=assistant.id,
        slug=assistant.slug,
        prospect_id=assistant.prospect_id,
        business_name=assistant.business_name,
        assistant_name=assistant.assistant_name,
        assistant_gender=ai_assistant_config_builder.resolve_persona_gender(assistant.assistant_name).value,
        email=assistant.email,
        languages=assistant.languages or [],
        tone=assistant.tone,
        accent_color=ai_assistant_service.accent_color(assistant),
        use_brand_color=assistant.use_brand_color,
        avatar_url=ai_assistant_avatar_service.public_url(assistant),
        avatar_enabled=assistant.avatar_enabled,
        avatar_is_transparent=bool(assistant.avatar_is_transparent),
        avatar_background=assistant.avatar_background,
        status=assistant.status,
        demo_url=ai_assistant_service.page_url(assistant.slug),
        embed_snippet=AiAssistantEmbedSnippet.render(assistant.slug),
        demo_link_sent_at=assistant.demo_link_sent_at,
        expires_at=assistant.expires_at,
        video_status=assistant.video_status,
        video_page_url=video_page_url(assistant.slug) if has_ready_video(assistant) else None,
        video_thumbnail_url=(
            public_thumbnail_url(assistant.slug, assistant.video_generated_at) if has_ready_video(assistant) else None
        ),
        video_error=assistant.video_error,
        video_generated_at=assistant.video_generated_at,
        video_desktop_requested_at=assistant.video_desktop_requested_at,
        is_video_desktop_build_started=assistant_video_service.is_desktop_build_started(assistant),
        is_video_made_with_older_clip=assistant_video_service.is_made_with_older_clip(assistant, clip_in_use_since),
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
        mailbox_enabled=bool(assistant.mailbox_enabled),
        mailbox_status=mailbox_view.connection,
        mailbox_address=mailbox_view.account_email,
        delivered_at=assistant.delivered_at,
        installed_at=assistant.installed_at,
        installed_host=assistant.installed_host,
        google_profile_linked_at=assistant.google_profile_linked_at,
        missing_start_steps=missing_start_steps,
        needs_follow_up=ai_assistant_start_reminders.needs_follow_up(assistant, missing_start_steps),
        unanswered_count=len(ai_assistant_faq_service.unanswered_of(assistant.knowledge_json)),
        created_at=assistant.created_at,
    )


def _start_steps_of(db: Session, assistant: AiAssistant) -> list[AiAssistantStartStep]:
    """The « Pour démarrer » steps a sold assistant still misses (a demo has none to take)."""
    if assistant.status != AiAssistantStatus.DELIVERED.value:
        return []
    return ai_assistant_start_reminders.missing_steps(db, assistant)


def _start_steps_by_assistant_id(db: Session, assistants: list[AiAssistant]) -> dict[int, list[AiAssistantStartStep]]:
    """The « Pour démarrer » steps each sold assistant of a list still misses, keyed by its id (a demo has none)."""
    sold = [assistant for assistant in assistants if assistant.status == AiAssistantStatus.DELIVERED.value]
    return ai_assistant_start_reminders.missing_steps_by_assistant_id(db, sold)


def _to_full_owner_response(db: Session, assistant: AiAssistant) -> AiAssistantResponse:
    """One assistant as the list shows it (subscription, counts, start steps and mailbox included), after an edit."""
    return _to_owner_response(
        assistant,
        assistant_subscription_service.live_by_assistant_ids(db, [assistant.id]).get(assistant.id),
        ai_assistant_conversation_service.counts_for_assistants(db, [assistant.id]).get(assistant.id),
        ai_assistant_request_service.counts_for_assistants(db, [assistant.id]).get(assistant.id),
        _start_steps_of(db, assistant),
        ai_assistant_mailbox_service.views_for_assistants(db, [assistant]).get(assistant.id),
        assistant_video_service.clip_in_use_since(db, assistant.user_id),
    )


def _refuse_while_desktop_builds(assistant: AiAssistant) -> None:
    """Refuse to withdraw or delete a video the owner's desktop app is building: it would publish it anyway."""
    if assistant_video_service.is_desktop_build_started(assistant):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ALREADY_BUILDING_MESSAGE)


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
    subscriptions = assistant_subscription_service.live_by_assistant_ids(db, [a.id for a in assistants])
    conversation_counts = ai_assistant_conversation_service.counts_for_assistants(db, [a.id for a in assistants])
    request_counts = ai_assistant_request_service.counts_for_assistants(db, [a.id for a in assistants])
    missing_start_steps = _start_steps_by_assistant_id(db, assistants)
    mailboxes = ai_assistant_mailbox_service.views_for_assistants(db, assistants)
    clip_in_use_since = assistant_video_service.clip_in_use_since(db, user.id)
    return AiAssistantListResponse(
        assistants=[
            _to_owner_response(
                assistant,
                subscriptions.get(assistant.id),
                conversation_counts.get(assistant.id),
                request_counts.get(assistant.id),
                missing_start_steps.get(assistant.id),
                mailboxes.get(assistant.id),
                clip_in_use_since,
            )
            for assistant in assistants
        ]
    )


@router.get("/{assistant_id:int}", response_model=AiAssistantResponse)
async def get_assistant(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """One of the caller's assistants, with its counters and subscription (the detail page)."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    return _to_full_owner_response(db, assistant)


@router.patch("/{assistant_id}", response_model=AiAssistantResponse)
async def update_assistant(
    assistant_id: int,
    payload: AiAssistantUpdateRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """
    Edit one of the caller's assistants (name, persona, languages, accent, owner alerts, EU only, mailbox switch).

    Switching the mailbox off disconnects the Gmail its client connected.
    """
    assistant = (
        db.query(AiAssistant)
        .filter(AiAssistant.id == assistant_id, AiAssistant.user_id == user.id, AiAssistant.deleted_at.is_(None))
        .first()
    )
    if not assistant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    was_mailbox_enabled = bool(assistant.mailbox_enabled)
    try:
        updated = ai_assistant_service.update(db, assistant, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    if was_mailbox_enabled and not updated.mailbox_enabled:
        await ai_assistant_mailbox_service.disconnect(db, updated)
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


@router.post("/{assistant_id}/client-link", response_model=AiAssistantClientLinkResponse)
async def issue_assistant_client_link(
    assistant_id: int,
    payload: AiAssistantClientLinkRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantClientLinkResponse:
    """A fresh client-space link for one of the caller's sold assistants, emailed to the business on demand."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    if assistant.status != AiAssistantStatus.DELIVERED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="L'espace client s'ouvre une fois l'assistant vendu."
        )
    delivery = await ai_assistant_client_space_service.issue_link(db, assistant, send=payload.send)
    return AiAssistantClientLinkResponse(
        url=delivery.url, expires_at=delivery.expires_at, sent_to=delivery.sent_to, send_error=delivery.send_error
    )


@router.post("/{assistant_id}/client-link/revoke", response_model=AiAssistantResponse)
async def revoke_assistant_client_links(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Stop every client-space link sent so far for one of the caller's sold assistants, alert SMS included."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    if assistant.status != AiAssistantStatus.DELIVERED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="L'espace client s'ouvre une fois l'assistant vendu."
        )
    ai_assistant_client_space_service.revoke_links(db, assistant, operator_email=user.email)
    return _to_full_owner_response(db, assistant)


@router.post("/{assistant_id}/deliver", response_model=AiAssistantResponse)
async def deliver_assistant(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """
    Mark one of the caller's demo assistants sold outside Stripe (paid by transfer, or the operator's own business):
    served for good, its owner alerted of each request, and the business welcomed like after a checkout.
    """
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    if assistant.status == AiAssistantStatus.DELIVERED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cet assistant est déjà vendu.")
    if assistant.status not in (AiAssistantStatus.ACTIVE.value, AiAssistantStatus.EXPIRED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Seule une démo active ou expirée peut être marquée vendue."
        )
    assistant_subscription_service.mark_assistant_sold(db, assistant.id)
    db.commit()
    db.refresh(assistant)
    activity_log_service.record(
        category=CATEGORY_ASSISTANT,
        action="assistant_marked_sold",
        status=STATUS_SUCCESS,
        title=f"{assistant.business_name} · assistant marqué vendu hors Stripe",
        detail=f"Par {user.email}",
        user_id=user.id,
        entity_type="prospect",
        entity_id=assistant.prospect_id,
    )
    await ai_assistant_client_space_service.try_send_welcome(db, assistant)
    return _to_full_owner_response(db, assistant)


@router.get("/{assistant_id}/video/state", response_model=ProspectionVideoStateResponse)
async def get_assistant_video_state(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> ProspectionVideoStateResponse:
    """Where the prospection video stands, for the dashboard to follow a PC build without reloading the assistant."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    is_video_ready = has_ready_video(assistant)
    clip_in_use_since = assistant_video_service.clip_in_use_since(db, user.id)
    return ProspectionVideoStateResponse(
        video_status=assistant.video_status,
        video_error=assistant.video_error,
        video_generated_at=assistant.video_generated_at,
        video_desktop_requested_at=assistant.video_desktop_requested_at,
        is_video_desktop_build_started=assistant_video_service.is_desktop_build_started(assistant),
        is_video_made_with_older_clip=assistant_video_service.is_made_with_older_clip(assistant, clip_in_use_since),
        video_page_url=video_page_url(assistant.slug) if is_video_ready else None,
        video_thumbnail_url=(
            public_thumbnail_url(assistant.slug, assistant.video_generated_at) if is_video_ready else None
        ),
    )


@router.get("/video/desktop-requests", response_model=list[AiAssistantDesktopVideoRequestResponse])
async def list_assistant_desktop_video_requests(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> list[AiAssistantDesktopVideoRequestResponse]:
    """Receptionist videos the caller's desktop app must build. Only the desktop app calls this."""
    desktop_app_presence.mark_seen(user.id)
    return [
        AiAssistantDesktopVideoRequestResponse(
            assistant_id=assistant.id,
            slug=assistant.slug,
            business_name=assistant.business_name,
            requested_at=assistant.video_desktop_requested_at,
        )
        for assistant in assistant_video_desktop_relay.waiting_subjects(db, user.id)
    ]


@router.post(
    "/{assistant_id}/video/desktop-request", response_model=AiAssistantResponse, status_code=status.HTTP_202_ACCEPTED
)
async def request_assistant_video_from_desktop(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Ask the owner's desktop app to build the prospection video (webcam speech + a recording of the widget)."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    try:
        assistant_video_desktop_relay.request(db, assistant, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_full_owner_response(db, assistant)


@router.delete("/{assistant_id}/video/desktop-request", response_model=AiAssistantResponse)
async def cancel_assistant_video_desktop_request(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Withdraw the video request left for the desktop app; a video already published is untouched."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    _refuse_while_desktop_builds(assistant)
    return _to_full_owner_response(db, assistant_video_desktop_relay.clear_request(db, assistant))


@router.post("/{assistant_id}/video/desktop-claim", response_model=AiAssistantResponse)
async def claim_assistant_video_desktop_request(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Tell that the caller's desktop app starts building the requested video, so nothing else takes it."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    try:
        assistant_video_desktop_relay.claim(assistant)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _to_full_owner_response(db, assistant)


@router.post("/{assistant_id}/video/desktop-failure", response_model=AiAssistantResponse)
async def report_assistant_video_desktop_failure(
    assistant_id: int,
    payload: ProspectionVideoDesktopFailureRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Close a requested video the desktop app could not build, with the reason the dashboard shows."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    try:
        assistant_video_desktop_relay.record_failure(db, assistant, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _to_full_owner_response(db, assistant)


@router.get("/{assistant_id}/video-context")
async def get_assistant_video_context(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Everything the desktop sidecar needs to render this assistant's video locally.

    Like every prospection video, it is built on the owner's PC to spare the shared VPS. The sidecar
    records the public widget answering, montages it with its bundled ffmpeg, and posts the finished
    clip back via ``POST /{id}/video-final``.
    """
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    if assistant.status != AiAssistantStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La vidéo ne peut être générée que pour une réceptionniste active.",
        )
    presenter = presenter_video_service.get_for_user(db, user.id, ASSISTANT_PRESENTER_MODULE)
    if presenter is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun clip de présentation « réceptionniste » enregistré.",
        )
    total_seconds = presenter.duration_seconds - presenter.intro_seconds - presenter.outro_seconds
    first_name: str | None = None
    if assistant.prospect_id:
        resolved_first, _last, _gender = EmailVariables.resolved_contact(db, assistant.prospect_id)
        first_name = resolved_first or None
    return {
        "slug": assistant.slug,
        "demo_url": ai_assistant_service.page_url(assistant.slug),
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
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    try:
        await assistant_video_service.store_desktop_video(db, assistant, file.file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except VideoGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return _to_full_owner_response(db, assistant_video_desktop_relay.clear_request(db, assistant))


@router.post("/{assistant_id}/avatar", response_model=AiAssistantResponse)
async def upload_assistant_avatar(
    assistant_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Keep an uploaded photo or logo (PNG, JPEG or WebP, 2 MB at most) as the receptionist's own portrait."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    try:
        updated = await ai_assistant_avatar_service.store(db, assistant, file)
    except AvatarRefusal as exc:
        refusal_status = (
            status.HTTP_413_CONTENT_TOO_LARGE if exc.is_too_large else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=refusal_status, detail=str(exc)) from exc
    except AvatarStorageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return _to_full_owner_response(db, updated)


@router.delete("/{assistant_id}/avatar", response_model=AiAssistantResponse)
async def clear_assistant_avatar(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Delete the receptionist's own portrait: it shows its casting face again."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    return _to_full_owner_response(db, await ai_assistant_avatar_service.clear(db, assistant))


@router.delete("/{assistant_id}/video", response_model=AiAssistantResponse)
async def clear_assistant_video(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AiAssistantResponse:
    """Delete the assistant's generated video and reset its state, its request to the desktop app withdrawn."""
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    _refuse_while_desktop_builds(assistant)
    assistant_video_service.clear_video(db, assistant)
    return _to_full_owner_response(db, assistant_video_desktop_relay.clear_request(db, assistant))


@router.delete("/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant(
    assistant_id: int,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Delete one of the caller's assistants, refused while a subscription still pays for it.

    It stops being served, its files and its visitors' data are erased, and its row stays for the sales history.
    """
    assistant = owned_assistant_or_404(db, assistant_id, user.id)
    if ai_assistant_purge_service.has_live_subscription(db, assistant):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Résiliez d'abord l'abonnement de cette réceptionniste."
        )
    assistant.status = AiAssistantStatus.DELETED.value
    assistant.deleted_at = naive_utc_now()
    db.commit()
    await ai_assistant_purge_service.purge(db, assistant)
